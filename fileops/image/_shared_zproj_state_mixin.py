import itertools
import logging
import threading
import time
import traceback

from fileops.image.exceptions import FrameNotFoundError
from fileops.image.ops import z_projection


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
        self._zcache_thread = None

    def init_shared(self, s_lock, s_state, s_queue):
        self._zcache_state = s_state
        self._zcache_priority = s_queue
        self._zcache_lock = s_lock
        self._zcache_thread = None

    def _zprj_populate_deque(self):
        if self._zcache_state is None:
            return
        for zkey in self._zcache_state.keys():
            cstate = self._zcache_state[zkey]
            if cstate['state'] == 'empty':
                self._zcache_priority.appendleft(zkey)

    def _zprj_thread(self):
        if self._zcache_thread is not None or len(self._zcache_priority) == 0:
            return

        self._zcache_thread = threading.Thread(
            target=_zproject,
            args=(self, self._zcache_state, self._zcache_priority, self._zcache_lock)
        )
        self._zcache_thread.start()

    def z_projection(self, frame: int, channel: int, projection='max', as_8bit=False):
        if self._zcache_state is None or self._zcache_priority is None:  # no cache system is currently in place
            self.log.warning(f"no cache system is currently in place for doing z-projections "
                             f"when invoked for frame:{frame} channel:{channel}")
            self.log.warning(traceback.format_exc())

            return z_projection(self, frame=frame, channel=channel, projection=projection, as_8bit=as_8bit)

        self.log.debug(f"z_projection frame:{frame} channel:{channel} "
                       f"deque_len:{len(self._zcache_priority)} "
                       f"state_len:{len(self._zcache_state)}")
        if len(self._zcache_state) == 0:
            self.log.debug("running z-projection for the first time.")
            for f, c in itertools.product(self.frames, self.channels):
                key = f"f{f:05d}_c{c:02d}"
                self._zcache_state[key] = {
                    'state':      'empty',
                    'projection': projection,
                    '8bit':       as_8bit,
                    'image':      None
                }
        self.precalc_z_projection(frame, channel, projection, as_8bit)

        key = f"f{frame:05d}_c{channel:02d}"
        self._zcache_lock.acquire()
        ckeyelem = self._zcache_state[key]
        if ckeyelem['state'] == 'done':
            self._zcache_lock.release()
            self.log.debug(f"retrieving z-projection that was already done for frame:{frame} channel:{channel}.")
            return ckeyelem['image']
        elif ckeyelem['state'] == 'empty':
            self.log.debug(f"z-projection not yet computed for frame:{frame} channel:{channel}.")
            self.log.debug(self._zcache_priority)
            if key in self._zcache_priority:
                self._zcache_priority.remove(key)
            self.log.debug(self._zcache_priority)
            ckeyelem['state'] = 'calculating'
            self._zcache_state[key] = ckeyelem
            self._zcache_lock.release()
            self.log.debug("computing z-projected image from scratch.")

            fr, ch = map(lambda s: int(s[1:]), key.split('_'))
            try:
                ckeyelem['image'] = z_projection(self, frame=fr, channel=ch, projection=projection, as_8bit=as_8bit)
                self.log.debug("image ready.")

                self._zcache_lock.acquire()
                ckeyelem['state'] = 'done'
                self._zcache_state[key] = ckeyelem
                self._zcache_lock.release()
            except FrameNotFoundError as e:
                self._zcache_lock.acquire()
                ckeyelem['state'] = 'fail'
                self._zcache_state[key] = ckeyelem
                self._zcache_lock.release()

            return ckeyelem['image']
        elif ckeyelem['state'] == 'calculating':
            self.log.debug(f"z-projection currently being computed for frame:{frame} channel:{channel}.")
            self._zcache_lock.release()

            self.log.debug("waiting for z-projected image to be ready.")
            timeout_s = 60
            t_start = time.time()
            t_end = time.time()
            state = ckeyelem['state']
            while t_end - t_start < timeout_s and state in ['calculating']:
                self.log.debug(f"not yet... {t_end - t_start} {timeout_s} state:{state}")
                time.sleep(0.1)
                ckeyelem = self._zcache_state[key]
                state = ckeyelem['state']
                t_end = time.time()

            ckeyelem = self._zcache_state[key]
            if ckeyelem['image'] is not None:
                return ckeyelem['image']
            else:
                raise FrameNotFoundError
        else:
            self._zcache_lock.release()
            self.log.debug(f"Not able to retrieve z-projection. Current state {ckeyelem['state']}")
            return None


def _zproject(image_file, zstate, priority, lock):
    while len(priority) > 0:
        image_file.log.debug(f"len(priority) = {len(priority)}.")

        lock.acquire()
        try:
            zkey = priority.pop()
        except IndexError:  # length of deque was zero even after checking the condition in the while loop! concurrency at its best!
            lock.release()
            continue

        fr, ch = map(lambda s: int(s[1:]), zkey.split('_'))
        ckeyelem = zstate[zkey]
        image_file.log.debug(ckeyelem['state'])
        if ckeyelem['state'] == 'empty':
            ckeyelem['state'] = 'calculating'
            zstate[zkey] = ckeyelem
            lock.release()

            try:
                ckeyelem['image'] = z_projection(image_file, frame=fr, channel=ch,
                                                 projection=ckeyelem['projection'],
                                                 as_8bit=ckeyelem['8bit'])
                lock.acquire()
                ckeyelem['state'] = 'done'
                zstate[zkey] = ckeyelem
                lock.release()
            except FrameNotFoundError as e:
                lock.acquire()
                ckeyelem['state'] = 'fail'
                zstate[zkey] = ckeyelem
                lock.release()


        else:
            lock.release()
    image_file.log.debug("bye")
