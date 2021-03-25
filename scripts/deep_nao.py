# -*- coding: utf-8 -*
"""

"""

__version__ = "0.0.1"

__copyright__ = "Copyright 2021, Aldebaran Robotics"
__author__ = 'Remi HUMBERT'
__email__ = 'rhumbert@softbankrobotics.com'

from functools import wraps
import stk.runner
import stk.events
import stk.services
import stk.worker
from stk.logging import get_logger, log_exceptions_and_return, log_exceptions
import qi
import sys
import motion
import almath
import time
import collections
import numpy
import vision_definitions
import base64
import os
from models import MobilenetV2SSD, TinyYoloV4
from translations import sentences

SERVICE_NAME="DeepNao"

BEHAVIOR="deep_nao/behavior"

if stk.runner.is_on_robot():
    # Special: for NAOqi OS, pre-compiled cv2 is packaged
    # patch path for local cv2, should only be run when on robot
    sys.path.insert(0, "lib/python2.7/site-packages")

import cv2


@qi.singleThreaded()
class Activity(object):

    APP_ID = "com.softbankrobotics.deep_nao"
    FOV_V = 0.7731809
    FOV_H = 0.963421747

    # When continuous describing the scene, do describe the same object only
    # after 60 seconds have passed.
    CONTINUOUS_DESCRIPTION_REPEAT_TIME = 60

    def __init__(self, qiapp):
        self.qiapp = qiapp
        self.logger = get_logger(qiapp.session, self.APP_ID)
        self.running = qi.Property("b")
        self.running.setValue(False)
        self.wait_for_dependency_services()
        self.events = stk.events.EventHelper(qiapp.session)
        self.services = stk.services.ServiceCache(qiapp.session)

        self.periodic_task = qi.PeriodicTask()
        self.periodic_task.setCallback(self.process_camera_image)
        self.periodic_task.compensateCallbackTime(False)
        # Run as fast as possible, network inference will slow it down
        self.periodic_task.setUsPeriod(1)
        self.subscriber_id = None

        self.topic_name = None
        self.uploaded_size = {}
        # Continuous description
        self.continuous_description = qi.Property("b")
        self.continuous_exploration = qi.Property("b")
        self.use_custom_model = qi.Property("b")



    @qi.nobind
    @log_exceptions
    def on_continuous_exploration_change(self, exploration_value):
        if exploration_value:
            self.services.Explorer.start()
        else:
            self.services.Explorer.stop()
            self.services.ALRobotPosture.goToPosture("Crouch", 1.0)
            self.services.ALMotion.rest()

    ## Handling loading of dependencies

    @qi.nobind
    @log_exceptions
    def wait_for_dependency_services(self):
        dependencies = [
            "ALDialog",
            "ALAutonomousLife",
            "ALTextToSpeech",
            "ALVideoDevice",
            "ALRobotPosture",
            "ALMotion",
            "Explorer",
            "StopBehaviorOnRobotFall",
        ]
        for service in dependencies:
            self.logger.info("Waiting for service %s" % service)
            self.qiapp.session.waitForService(service)

    #####################################
    ## Service start / stop management ##
    #####################################

    @qi.nobind
    @stk.events.on("AutonomousLife/FocusedActivity")
    @log_exceptions
    def on_focus_change(self, activity):
        #if not self.robot_has_fallen.value():
        if activity == BEHAVIOR:
            self.start_behavior()
        else:
            self.stop_behavior()

    @qi.nobind
    @log_exceptions
    @stk.events.on("ALTextToSpeech.languageTTS")
    def on_language_change(self, value):
        if value == "fr_FR":
            value = "French"
        else:
            value = "English"
        self.language = value
        self.net.reload_classes(value)

    @qi.nobind
    @log_exceptions
    def on_start(self):
        self.events.connect_decorators(self)
        # clean any previous subscribtion (on re-install or restart)
        self.unsubscribe_all()
        use_model_pref = self.services.ALPreferenceManager.getValue(
            "com.softbankrobotics.deep_nao", "use_custom_model")
        try:
            use_model_pref = bool(int(use_model_pref))
        except:
            use_model_pref = False
        self.logger.info("Use model pref: %s" % use_model_pref)
        use_model_pref = use_model_pref and self.isCustomModelAvailable()
        self.logger.info("Use model pref with custom model: %s" % use_model_pref)
        self.use_custom_model.setValue(bool(use_model_pref))
        self.use_custom_model.connect(self.use_custom_model_changes)

        self.services.ALMemory.raiseEvent("DeepNao/RobotFallen", "False")

        if self.services.ALAutonomousLife.focusedActivity() == BEHAVIOR:
            self.start_behavior()


    @qi.nobind
    @log_exceptions
    def on_stop(self):
        "Cleanup"
        self.stop_behavior()
        self.logger.info("Application finished.")
        self.events.clear()

    @qi.nobind
    @log_exceptions
    def start_behavior(self):
        if self.running.value():
            return
        self.logger.info("Start behavior.")
        self.running.setValue(True)
        try:
            self.described_objects_time = {}
            self.move_head_state = 0
            self.continuous_description.setValue(False)
            self.continuous_exploration.setValue(False)
            self.explore_link = self.continuous_exploration.connect(
                self.on_continuous_exploration_change)

            self.language = self.services.ALTextToSpeech.getLanguage()

            if self.use_custom_model.value():
                if not self.load_custom_yolov4_network():
                    self.load_mobilenetv2_ssd_network()
            else:
                self.load_mobilenetv2_ssd_network()

            self.services.ALAutonomousLife.setAutonomousAbilityEnabled("BackgroundMovement", False)
            self.services.ALAutonomousLife.setAutonomousAbilityEnabled("BasicAwareness", False)
            self.services.ALRobotPosture.goToPosture("Crouch", 1.0)
            self.services.ALMotion.rest()
            self.services.ALTextToSpeech.say(sentences[self.language]["ready"])
            self.subscribe_to_camera()
            self.periodic_task.start(True)
        except Exception, e:
            self.logger.error(e)
            self.stop_behavior()
            self.running.setValue(False)


    @log_exceptions
    def stop_behavior(self):
        self.logger.info("Stop behavior.")
        try:
            self.services.Explorer.stop()
            self.continuous_exploration.disconnect(self.explore_link)
            self.continuous_exploration.setValue(False)
            self.continuous_description.setValue(False)
            self.periodic_task.stop()
            self.unsubscribe_from_camera()
        finally:
            self.running.setValue(False)


    #######################
    # Deep Models loading #
    #######################

    @qi.nobind
    @log_exceptions
    def load_mobilenetv2_ssd_network(self):
        classes = {
            "French": "models/ssd_mobilenet_v2_oid_v4/objects.names.fr",
            "English": "models/ssd_mobilenet_v2_oid_v4/objects.names.en"
        }
        self.net = MobilenetV2SSD(
            "models/ssd_mobilenet_v2_oid_v4/frozen_inference_graph.pb",
            "models/ssd_mobilenet_v2_oid_v4/graph.pbtxt",
            classes,
            self.language)
        self.logger.info("Net loaded, found classes: %s" % self.net.classes)



    CUSTOM_MODEL_CONFIG = "models/yolo_v4_tiny_custom/model.cfg"
    CUSTOM_MODEL_WEIGHT = "models/yolo_v4_tiny_custom/model.weights"
    CUSTOM_MODEL_NAMES_FR = "models/yolo_v4_tiny_custom/objects.names.fr"
    CUSTOM_MODEL_NAMES_EN = "models/yolo_v4_tiny_custom/objects.names.en"

    @log_exceptions
    def isCustomModelAvailable(self):
        return os.path.exists(self.CUSTOM_MODEL_CONFIG) \
          and os.path.exists(self.CUSTOM_MODEL_WEIGHT) \
          and os.path.exists(self.CUSTOM_MODEL_NAMES_FR) \
          and os.path.exists(self.CUSTOM_MODEL_NAMES_EN)

    @qi.nobind
    @log_exceptions
    def use_custom_model_changes(self, value):
        self.services.ALPreferenceManager.setValue(
            "com.softbankrobotics.deep_nao", "use_custom_model", value)
        if self.running.value():
            if self.use_custom_model.value():
                if not self.load_custom_yolov4_network():
                    self.use_custom_model.setValue(False)
                    return
            else:
                self.load_mobilenetv2_ssd_network()
            self.services.ALTextToSpeech.say(sentences[self.language]["ready"])

    @qi.nobind
    @log_exceptions
    def load_custom_yolov4_network(self):
        classes = {
            "French": self.CUSTOM_MODEL_NAMES_FR,
            "English": self.CUSTOM_MODEL_NAMES_EN,
        }
        try:
            self.net = TinyYoloV4(
                self.CUSTOM_MODEL_WEIGHT,
                self.CUSTOM_MODEL_CONFIG,
                classes,
                self.language
            )
        except Exception, e:
            self.logger.error("Error loading custom model: %s" % (e))
            self.services.ALTextToSpeech.say(sentences[self.language]["error_custom"])
            self.remove_custom_model()
            return False

        self.logger.info("Net loaded, found classes: %s" % self.net.classes)
        return True

    def remove_custom_model(self):
        if os.path.exists(self.CUSTOM_MODEL_CONFIG):
            os.remove(self.CUSTOM_MODEL_CONFIG)
        if os.path.exists(self.CUSTOM_MODEL_WEIGHT):
            os.remove(self.CUSTOM_MODEL_WEIGHT)
        if os.path.exists(self.CUSTOM_MODEL_NAMES_FR):
            os.remove(self.CUSTOM_MODEL_NAMES_FR)
        if os.path.exists(self.CUSTOM_MODEL_NAMES_EN):
            os.remove(self.CUSTOM_MODEL_NAMES_EN)


    ###########################
    # Camera image processing #
    ###########################

    @qi.nobind
    @log_exceptions
    def subscribe_to_camera(self):
        fps = 2
        self.subscriber_id = self.services.ALVideoDevice.subscribeCamera(
            self.APP_ID,
            vision_definitions.kTopCamera,
            vision_definitions.kVGA,
            vision_definitions.kBGRColorSpace,
            fps
        )

    @qi.nobind
    @log_exceptions
    def unsubscribe_from_camera(self):
        self.logger.info("Unsubscribe from camera")
        if self.subscriber_id is not None:
            self.services.ALVideoDevice.unsubscribe(self.subscriber_id)
            self.subscriber_id = None
            self.logger.info("Unsubscribe done")
        else:
            self.logger.info("Nothing to unsubscribe")

    @qi.nobind
    @log_exceptions
    def process_camera_image(self):
        #self.logger.info("Process camera image")

        image_remote = self.services.ALVideoDevice.getImageRemote(self.subscriber_id)
        if not image_remote:
            raise Exception("No data in image")

        width = image_remote[0]
        height = image_remote[1]
        channels = image_remote[2]
        colorspace = image_remote[3]
        data = image_remote[6]

        #self.logger.info("Got image %sx%sx%s %s" % (width, height, channels, colorspace))

        imageBGR = numpy.frombuffer(data, dtype = numpy.uint8).reshape(height, width, channels)

        self.services.ALVideoDevice.releaseImage(self.subscriber_id)

        start_time = time.time()
        imageBGR = self.net.label_image_content(imageBGR)
        end_time = time.time()
        self.logger.info("Inference time: %s" % (end_time - start_time))

        if self.continuous_description.value() or self.continuous_exploration.value():
            self.continuousDescribeObjects()

        path = "/home/nao/.local/share/PackageManager/apps/deep_nao/html/img/deep.jpg"
        cv2.imwrite(path, imageBGR, [cv2.IMWRITE_JPEG_QUALITY, 55])


    @qi.nobind
    @log_exceptions
    def unsubscribe_all(self):
        self.logger.info("_unsubscribe_all...")
        for subscriber_id in self.services.ALVideoDevice.getSubscribers():
            if subscriber_id.startswith(self.APP_ID):
                self.services.ALVideoDevice.unsubscribe(subscriber_id)
        self.logger.info("_unsubscribe_all done")


    ##########################
    # Web interface commands #
    ##########################

    @qi.nobind
    @log_exceptions
    def remove_head_stiffness(self):
        self.services.ALMotion.setStiffnesses(['HeadYaw', 'HeadPitch'], 0.0)

    @stk.worker.async("move_head", 2, 0)
    @log_exceptions
    def webLookAt(self, x, y):
        if hasattr(self, "remove_stiffness_future") \
          and self.remove_stiffness_future.isRunning():
            self.remove_stiffness_future.cancel()
        delta_yaw = -x * self.FOV_H / 2
        delta_pitch = -y * self.FOV_V / 2
        self.last_lookat_time = time.time()
        self.services.ALMotion.setStiffnesses(['HeadYaw', 'HeadPitch'], 0.5)
        self.services.ALMotion.angleInterpolation(
            ['HeadYaw', 'HeadPitch'], [delta_yaw, delta_pitch], [1, 1], False)
        self.remove_stiffness_future = qi.async(self.remove_head_stiffness, delay=2000*1000)


    @stk.worker.async("describe_objects", 2, 0)
    @log_exceptions
    def describeVisibleObjects(self):
        if self.net.last_visible_objects:
            sentence = sentences[self.language]["I_see"]
            for obj, num in self.net.last_visible_objects.iteritems():
                sentence += "%s %s" % (num, obj)
        else:
            sentence = sentences[self.language]["see_no_objects"]

        self.services.ALTextToSpeech.say(sentence)


    ##########################
    # Continuous description #
    ##########################

    @qi.nobind
    @log_exceptions
    def look_front(self):
        self.services.ALMotion.setStiffnesses(['HeadYaw'], 1.0)
        self.services.ALMotion.angleInterpolation("HeadYaw", 0, 1, True)
        self.services.ALMotion.setStiffnesses(['HeadYaw'], 0.0)

    @qi.nobind
    @log_exceptions
    def look_left(self):
        self.services.ALMotion.setStiffnesses(['HeadYaw'], 1.0)
        self.services.ALMotion.angleInterpolation("HeadYaw", 0.45, 1, True)
        self.services.ALMotion.setStiffnesses(['HeadYaw'], 0.0)

    @qi.nobind
    @log_exceptions
    def look_right(self):
        self.services.ALMotion.setStiffnesses(['HeadYaw'], 1.0)
        self.services.ALMotion.angleInterpolation("HeadYaw", -0.45, 1, True)
        self.services.ALMotion.setStiffnesses(['HeadYaw'], 0.0)


    @qi.nobind
    @log_exceptions
    def move_head_to_search_for_objects(self):
        current_time = time.time()

        if not hasattr(self, "last_described_time"):
            # Init last_described_time if it does not exists
            self.last_described_time = current_time
            return

        elapsed_time = current_time - self.last_described_time
        self.logger.info("Move head: %s, head state: %s %s"
                         % (elapsed_time, self.move_head_state, self.last_described_time))

        if elapsed_time > 12:
            self.look_front()
            self.move_head_state = 0
            self.last_described_time = current_time
        elif self.move_head_state == 0 and elapsed_time > 3:
            self.look_left()
            self.move_head_state = 1
        elif self.move_head_state == 1 and elapsed_time > 6:
            self.look_front()
            self.move_head_state = 2
        elif self.move_head_state == 2 and elapsed_time > 9:
            self.look_right()
            self.move_head_state = 3


    @stk.worker.async("describe_objects", 2, 0)
    @log_exceptions
    def continuousDescribeObjects(self):
        # If no objects to describe, return
        if not self.net.last_visible_objects:
            self.move_head_to_search_for_objects()
            return

        # Remove objects already describe recently
        objets_to_describe = self.net.last_visible_objects.copy()
        current_time = time.time()
        self.logger.info(self.described_objects_time)
        for obj, t in self.described_objects_time.items():
            if current_time - t < self.CONTINUOUS_DESCRIPTION_REPEAT_TIME:
                if obj in objets_to_describe:
                    del objets_to_describe[obj]
            else:
                del self.described_objects_time[obj]

        # If no objects to describe, return
        if not objets_to_describe:
            self.move_head_to_search_for_objects()
            return

        # Generate the sentence with objects
        sentence = sentences[self.language]["I_see"]
        for obj, num in objets_to_describe.iteritems():
                sentence += "%s %s" % (num, obj)

        # Describe
        self.services.ALTextToSpeech.say(sentence)

        current_time = time.time()

        # Record time when objects were described
        for obj, n in objets_to_describe.iteritems():
            self.described_objects_time[obj] = current_time

        self.last_described_time = current_time
        self.move_head_state = 0


    ##############################
    # Web upload of custom model #
    ##############################

    FILE_TYPE_TO_FILENAME = {
        "config": CUSTOM_MODEL_CONFIG,
        "weights": CUSTOM_MODEL_WEIGHT,
        "names_fr": CUSTOM_MODEL_NAMES_FR,
        "names_en": CUSTOM_MODEL_NAMES_EN,
    }

    @log_exceptions
    def startUpload(self, file_type):
        if not file_type in self.FILE_TYPE_TO_FILENAME:
            raise RuntimeError("Unknown filetype")
        with open(self.FILE_TYPE_TO_FILENAME[file_type], "w") as out:
            out.truncate(0)
        self.uploaded_size[file_type] = 0

    @log_exceptions
    def uploadChunk(self, chunk, offset, file_type):
        if not file_type in self.FILE_TYPE_TO_FILENAME:
            raise RuntimeError("Unknown filetype")
        data = base64.b64decode(chunk)
        with open(self.FILE_TYPE_TO_FILENAME[file_type], "r+") as out:
            out.seek(offset)
            out.write(data)
        self.uploaded_size[file_type] += len(data)

    @log_exceptions
    def finishUpload(self, filesize, file_type):
        if not file_type in self.uploaded_size:
            raise RuntimeError("Unknown filetype")
        if filesize != self.uploaded_size[file_type]:
            self.logger.error("Uploaded file size differ: %s %s"
                              % (filesize, self.uploaded_size[file_type]))
            if os.path.exists(self.FILE_TYPE_TO_FILENAME[file_type]):
                os.remove(self.FILE_TYPE_TO_FILENAME[file_type])
            raise RuntimeError("Bad size")
        else:
            self.logger.info("Upload of %s is done" % file_type)


if __name__ == "__main__":
    stk.runner.run_activity(Activity, SERVICE_NAME)
