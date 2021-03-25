import qi
import stk.runner
import stk.events
import stk.services
from stk.logging import get_logger, log_exceptions_and_return, log_exceptions

SERVICE_NAME="StopBehaviorOnRobotFall"

@qi.singleThreaded()
class Activity(object):

    APP_ID = "com.sotfbankrobotics.stop_behavior_on_fall"


    def __init__(self, qiapp):
        self.qiapp = qiapp
        self.events = stk.events.EventHelper(qiapp.session)
        self.s = stk.services.ServiceCache(qiapp.session)
        self.logger = get_logger(qiapp.session, self.APP_ID)
        self.wait_for_dependency_services()
        self.behavior_running = set([])
        self.behavior_list = [
            "deep_nao/behavior",
        ]
        self.robot_posture_check_task = qi.PeriodicTask()
        self.robot_posture_check_task.setCallback(self.check_robot_posture_after_fall)
        self.robot_posture_check_task.compensateCallbackTime(False)
        self.robot_posture_check_task.setUsPeriod(500)
        self.s.ALMemory.raiseEvent("DeepNao/RobotFallen", "False")

    @qi.nobind
    def wait_for_dependency_services(self):
        dependencies = [
            "ALBehaviorManager",
            "ALMemory",
        ]
        for service in dependencies:
            self.logger.info("Waiting for service %s" % service)
            self.qiapp.session.waitForService(service)

    def add_behavior_to_stop(self, behavior):
        self.behavior_list.append(behavior)

    @qi.nobind
    def on_start(self):
        self.events.connect_decorators(self)
        self.started_link = self.s.ALBehaviorManager.behaviorStarted.connect(self.on_behavior_started)
        self.stopped_link = self.s.ALBehaviorManager.behaviorStopped.connect(self.on_behavior_stopped)

    @qi.nobind
    def on_stop(self):
        "Cleanup"
        self.logger.info("Application finished.")
        self.events.clear()
        self.s.ALBehaviorManager.behaviorStarted.disconnect(self.started_link)
        self.s.ALBehaviorManager.behaviorStopped.disconnect(self.stopped_link)

    @stk.events.on("robotHasFallen")
    def on_robot_has_fallen(self, unused):
        self.s.ALMemory.raiseEvent("DeepNao/RobotFallen", "True")
        for behavior in self.behavior_running:
            self.logger.info("STOPPING: %s" % behavior)
            self.s.ALBehaviorManager.stopBehavior(behavior)
        self.robot_posture_check_task.start(True)

    def on_behavior_started(self, behavior):
        self.logger.info("start %s" % behavior)
        if behavior in self.behavior_list:
            self.behavior_running.add(behavior)

    def on_behavior_stopped(self, behavior):
        self.logger.info("stop %s" % behavior)
        if behavior in self.behavior_list:
            self.behavior_running.remove(behavior)

    @qi.nobind
    @log_exceptions
    def check_robot_posture_after_fall(self):
        posture = self.s.ALRobotPosture.getPosture()
        if posture in [
            "Crouch",
            "Sit",
            "SitRelax",
            "Stand",
            "StandInit",
            "StandZero"
        ]:
            self.robot_posture_check_task.stop()
            self.s.ALMemory.raiseEvent("DeepNao/RobotFallen", "False")


if __name__ == "__main__":
    stk.runner.run_activity(Activity, SERVICE_NAME)
