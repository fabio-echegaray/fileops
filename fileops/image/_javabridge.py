import bioformats as bf
import javabridge

from fileops.logger import get_logger


def create_jvm():
    log = get_logger(name='create_jvm')
    log.debug("Starting javabridge JVM to be used by the bioformats package.")
    log.debug("Limit 1G for heap.")

    javabridge.start_vm(class_path=bf.JARS, max_heap_size="1G", run_headless=True)
    env = javabridge.attach()

    # Forbid Javabridge to spill out DEBUG messages during runtime from CellProfiler/python-bioformats.
    root_logger_name = javabridge.get_static_field("org/slf4j/Logger",
                                                   "ROOT_LOGGER_NAME",
                                                   "Ljava/lang/String;")
    root_logger = javabridge.static_call("org/slf4j/LoggerFactory",
                                         "getLogger",
                                         "(Ljava/lang/String;)Lorg/slf4j/Logger;",
                                         root_logger_name)
    log_level = javabridge.get_static_field("ch/qos/logback/classic/Level",
                                            "WARN",
                                            "Lch/qos/logback/classic/Level;")
    javabridge.call(root_logger,
                    "setLevel",
                    "(Lch/qos/logback/classic/Level;)V",
                    log_level)

    return env
