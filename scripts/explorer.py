import random
import time
import math
import qi
import stk.runner
import stk.events
import stk.services
import stk.worker
from stk.logging import get_logger, log_exceptions_and_return, log_exceptions

logger = qi.logging.Logger('com.softbankrobotics.deep_nao.explorer')

# Sleep time at the end of the sonar loop
SONAR_PERIOD = 0.1

# Distance at which to stop in fron of obstacles
OBSTACLE_DISTANCE = 0.4

EXPLORATION_WALK_SPEED = 1.0

NOWHERE, LEFT, RIGHT, FRONT = range(4)

SERVICE_NAME="Explorer"

@qi.singleThreaded()
class Explorer(object):

    def __init__(self, qiapp):
        self.qiapp = qiapp
        self.wait_for_dependency_services()
        self.services = stk.services.ServiceCache(qiapp.session)
        self.logger = logger

        # We keep track of a very rough estimate of the current deviation from the
        # original direction to avoid the robot to try to turn right, then turn left,
        # then turn right etc. (i.e. to seem stuck in a corner of the room)
        self.deviation = 0
        self.runningFuture = None
        self.isRunning = False

    ## Handling loading of dependencies

    @qi.nobind
    @log_exceptions
    def wait_for_dependency_services(self):
        dependencies = [
            "ALRobotPosture",
            "ALMemory",
            "ALMotion",
        ]
        for service in dependencies:
            logger.info("Waiting for service %s" % service)
            self.qiapp.session.waitForService(service)

    @qi.nobind
    @log_exceptions
    def get_obstacle_position(self, sonarLeft, sonarRight):
        left = sonarLeft < OBSTACLE_DISTANCE
        right = sonarRight < OBSTACLE_DISTANCE
        if left and right:
            return FRONT
        if left:
            return LEFT
        if right:
            return RIGHT
        return NOWHERE

    @log_exceptions
    def start(self):
        if self.isRunning:
            return
        self.mustStop = False
        self.runningFuture = qi.async(lambda: self.run())


    @log_exceptions
    def stop(self):
        if not self.isRunning:
            return
        self.mustStop = True
        self.services.ALMotion.stopMove()
        if self.runningFuture is not None:
            self.runningFuture.wait()
            self.runningFuture = None

    @qi.nobind
    @log_exceptions
    def run(self):
        self.isRunning = True
        try:
            # To make sure arms are not in front of the sonar
            self.services.ALRobotPosture.goToPosture('StandInit', 0.75)

            while not self.mustStop:

                if not self.services.ALMotion.moveIsActive():
                    self.services.ALMotion.moveToward(EXPLORATION_WALK_SPEED, 0, 0)

                    # Look ahead
                    self.services.ALMotion.setAngles(['HeadYaw', 'HeadPitch'], [0.0, 0.0], 0.25)

                sonarLeft = self.services.ALMemory.getData("Device/SubDeviceList/US/Left/Sensor/Value")
                sonarRight = self.services.ALMemory.getData("Device/SubDeviceList/US/Right/Sensor/Value")

                p = self.get_obstacle_position(sonarLeft, sonarRight)
                if p != NOWHERE:
                    self.on_obstacle(p)

                time.sleep(0.1)

            self.services.ALMotion.stopMove()
        finally:
            self.isRunning = False


    @qi.nobind
    @log_exceptions
    def on_obstacle(self, p):
        #time.sleep(WAIT_BEFORE_HANDLING)

        if p == LEFT:
            x, y, theta = 0, 0, -self.angle_side()
        elif p == RIGHT:
            x, y, theta = 0, 0, self.angle_side()
        elif p == FRONT:
            if self.deviation == 0:
                sign = random.choice([-1 ,1])
            else:
                sign = math.copysign(1, self.deviation)
            x, y, theta = 0, 0, sign * random.uniform(math.pi/2, 3*math.pi/4)

        if self.mustStop:
            return

        headAngle = math.copysign(1, theta) * math.pi/4
        qi.async(self.services.ALMotion.angleInterpolationWithSpeed, 'HeadYaw',
            [headAngle, -headAngle], 0.25)

        if self.mustStop:
            return

        self.services.ALMotion.moveTo([(-0.1, 0, 0), (x, y, theta)])

        self.deviation += math.copysign(1, theta)
        if abs(self.deviation) >= 4:
            self.deviation = 0


    # Function used to pick a random angle when an obstacle is detected on
    # the side. (We often want small angles, hence the weird triangular
    # distribution)
    @qi.nobind
    @log_exceptions
    def angle_side(self):
        return random.triangular(math.pi/6, math.pi/2, math.pi/4)


if __name__ == "__main__":
    stk.runner.run_activity(Explorer, SERVICE_NAME)
