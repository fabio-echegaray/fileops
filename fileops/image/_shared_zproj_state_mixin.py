import itertools
import logging
import signal
import threading
import time
import traceback
from typing import TYPE_CHECKING

import numpy as np

import fileops
from fileops.image.exceptions import FrameNotFoundError
from fileops.image.ops import z_projection

if TYPE_CHECKING:
    from fileops.image import ImageFile


def exit_signal_handler(signum, frame):
    fileops.log.debug("Setting exiting event")
    if hasattr(fileops, "__IS_EXITING"):
        is_exiting = getattr(fileops, "__IS_EXITING")
        is_exiting.set()


class SharedStateZProjectionMixin:
    log: logging.Logger

    def __init__(self, *args, **kwargs):
        """
        Constructor of shared-data mixin
        The idea is to store z-projected images and requests to project the data in pickable, global variables.
        """
        super().__init__(*args, **kwargs)
        self.log.debug(f"Image file class created at {hex(id(self))}")

        # cache of images across different processes
        self._zcache_state = None
        self._zcache_priority = None
        self._zcache_lock = None
        self._zcache_semaphore = None
        self._zcache_thread = None

    def init_shared(self, s_lock, s_state_dict, s_list, s_semaphore):
        self._zcache_state = s_state_dict
        self._zcache_priority = s_list
        self._zcache_lock = s_lock
        self._zcache_semaphore = s_semaphore
        self._zcache_thread = None

    def _zprj_populate_state(self, projection='max', z_subset=None, as_8bit=False):
        self: ImageFile
        if len(self._zcache_priority) > 0:
            return
        frames = self.frame_subset if self.frame_subset is not None else self.frames
        channels = self.channel_subset if self.channel_subset is not None else self.channels
        for f, c in itertools.product(frames, channels):
            key = f"f{f:05d}_c{c:02d}"
            self._zcache_state[key] = {
                'state':         'empty',
                'waiting_since': None,
                'projection':    projection,
                'z_subset':      z_subset if z_subset is not None else self.z_subset,
                '8bit':          as_8bit,
                'image':         None
            }
            self._zcache_priority.append(key)
        self._zcache_priority = self._zcache_priority[20:]

    def _zprj_thread(self):
        if self._zcache_thread is not None or len(self._zcache_priority) == 0:
            return

        self._zcache_thread = threading.Thread(
            target=_zproject,
            args=(self, self._zcache_state, self._zcache_priority, self._zcache_lock, self._zcache_semaphore)
        )
        signal.signal(signal.SIGTERM, exit_signal_handler)
        self._zcache_thread.start()

    def z_projection(self, frame: int, channel: int, *args, projection='max', z_subset=None, as_8bit=False, **kwargs):
        self: ImageFile

        try:
            if hasattr(fileops, "__IS_EXITING"):
                is_exiting = getattr(fileops, "__IS_EXITING")
                if is_exiting.is_set():
                    self.log.debug("exiting...")
                    return None
        except AttributeError as e:
            return None

        if self._zcache_state is None or self._zcache_priority is None:  # no cache system is currently in place
            self.log.warning(f"no cache system is currently in place for doing z-projections "
                             f"when invoked for frame:{frame} channel:{channel}")
            self.log.warning(traceback.format_exc())

            mdiz = z_projection(self, frame, channel, projection=projection, as_8bit=as_8bit)
            return mdiz

        self.log.debug(f"z_projection frame:{frame} channel:{channel} "
                       f"deque_len:{len(self._zcache_priority)} "
                       f"state_len:{len(self._zcache_state)}")
        if len(self._zcache_state) == 0:
            self.log.debug("populating z-projection state structure for the first time.")
            self._zprj_populate_state()

        self._zprj_thread()

        key = f"f{frame:05d}_c{channel:02d}"
        self._zcache_lock.acquire()
        ckeyelem = self._zcache_state[key]
        self._zcache_lock.release()

        if ckeyelem['state'] == 'done':
            self.log.debug(f"retrieving z-projection that was already done for frame:{frame} channel:{channel}.")
            mdi = ckeyelem['image']
            # erase image in state to preserve memory
            ckeyelem['image'] = None
            ckeyelem['state'] = 'used'

            self._zcache_lock.acquire()
            self._zcache_state[key] = ckeyelem
            self._zcache_lock.release()

            return mdi
        elif ckeyelem['state'] == 'empty':
            # move key to beginning of priority list!
            self._zcache_lock.acquire()
            if key in self._zcache_priority:
                self._zcache_priority.insert(0, self._zcache_priority.pop(self._zcache_priority.index(key)))
            self._zcache_lock.release()

        if ckeyelem['state'] == 'calculating' or ckeyelem['state'] == 'empty':
            self.log.debug(f"z-projection currently being computed for frame:{frame} channel:{channel}. "
                           f"Waiting for z-projected image to be ready.")
            timeout_s = 120
            t_start = time.time()
            t_end = time.time()
            state = ckeyelem['state']
            while t_end - t_start < timeout_s and state in ['calculating', 'empty']:
                if hasattr(fileops, "__IS_EXITING"):
                    is_exiting = getattr(fileops, "__IS_EXITING")
                    if is_exiting.is_set():
                        self.log.debug("exiting from calculation loop...")
                        return None

                self.log.debug(
                    f"not yet... frame:{frame} channel:{channel} ∆T:{t_end - t_start:0.1f}({timeout_s}) state:{state}")
                time.sleep(2)
                ckeyelem = self._zcache_state[key]
                state = ckeyelem['state']
                t_end = time.time()

            ckeyelem = self._zcache_state[key]
            if ckeyelem['image'] is not None:
                mdi = ckeyelem['image']

                # erase image in state to preserve memory
                ckeyelem['image'] = None
                self._zcache_lock.acquire()
                ckeyelem['state'] = 'used'
                self._zcache_state[key] = ckeyelem
                self._zcache_lock.release()

                return mdi
            else:
                raise FrameNotFoundError
        else:
            self._zcache_lock.release()
            self.log.debug(f"Not able to retrieve z-projection. Current state {ckeyelem['state']}")
            raise FrameNotFoundError


def _zproject(image_file, zstate, priority, lock, sem):
    if not sem.acquire(blocking=False):
        image_file.log.debug("failed attempt to run _zproject thread.")
        return
    image_file.log.debug("starting _zproject thread.")

    while len(priority) > 0:
        if hasattr(fileops, "__IS_EXITING"):
            is_exiting = getattr(fileops, "__IS_EXITING")
            if is_exiting.is_set():
                image_file.log.debug("_zproject thread exiting...")
                break

        image_file.log.debug(f"Z-project thread loop with objs at memory addresses: "
                             f"s_lock({hex(id(lock))}), s_state({hex(id(zstate))}), s_queue({hex(id(priority))})."
                             f"Queue len(priority) = {len(priority)}.")

        if not lock.acquire(timeout=10):
            continue
        # wait if too many images are waiting in the queue to being used
        imgs_done = np.sum([1 for key, item in zstate.items() if item['state'] == 'done'])
        lock.release()
        while imgs_done >= 20:
            lock.acquire()
            keys_waiting = [key for key, item in zstate.items() if item['state'] == 'done']
            lock.release()

            image_file.log.debug(f"Z-project thread loop will wait for images to be consumed. "
                                 f"Currently there are {imgs_done} images in queue out of  list of {len(priority)}. "
                                 f"Keys waiting: {keys_waiting}")
            time.sleep(10)

            lock.acquire()
            imgs_done = np.sum([1 for key, item in zstate.items() if item['state'] == 'done'])

            # cleanup unused images if they have waited for too long
            curr_time = time.time()
            for key in keys_waiting:
                ckeyelem = zstate[key]
                s_time = ckeyelem["waiting_since"]
                if s_time is None:
                    continue
                if curr_time - s_time > 20:  # 20 second to wait for an image to be consumed
                    image_file.log.debug(f"freeing image at key={key}")
                    if zkey in priority:
                        priority.remove(zkey)
                    ckeyelem["state"] = "empty"
                    ckeyelem["image"] = None
                    ckeyelem["waiting_since"] = None
                    zstate[key] = ckeyelem
            lock.release()

        if not lock.acquire(timeout=10):
            continue
        try:
            zkey = priority.pop(0)
        except IndexError:  # length of deque was zero even after checking the condition in the while loop! concurrency at its best!
            lock.release()
            continue

        fr, ch = map(lambda s: int(s[1:]), zkey.split('_'))
        ckeyelem = zstate[zkey]
        image_file.log.debug(f"Z-project thread loop dealing with state: {ckeyelem['state']} in frame {fr} ch {ch}.")
        if ckeyelem['state'] == 'empty':
            ckeyelem['state'] = 'calculating'
            zstate[zkey] = ckeyelem
            lock.release()

            try:
                ckeyelem['image'] = z_projection(image_file, frame=fr, channel=ch,
                                                 projection=ckeyelem['projection'],
                                                 z_subset=ckeyelem['z_subset'],
                                                 as_8bit=ckeyelem['8bit'])
                ckeyelem['state'] = 'done'
                ckeyelem["waiting_since"] = time.time()

                lock.acquire()
                zstate[zkey] = ckeyelem
                lock.release()
            except FrameNotFoundError as e:
                ckeyelem['state'] = 'fail'

                lock.acquire()
                zstate[zkey] = ckeyelem
                lock.release()
            except (KeyError, SystemExit) as e:  # KeyboardInterrupt while in loop? Shutdown in process.
                break
        else:
            lock.release()
    image_file.log.debug("bye")
    sem.release()
