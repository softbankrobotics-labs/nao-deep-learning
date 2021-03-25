import sys
import stk.runner
if stk.runner.is_on_robot():
    # Special: for NAOqi OS, pre-compiled cv2 is packaged
    # patch path for local cv2, should only be run when on robot
    sys.path.insert(0, "lib/python2.7/site-packages")

import cv2
import unicodedata
import numpy

def strip_accents(unicode_text):
   text = unicodedata.normalize('NFD', unicode_text).encode('ascii', 'ignore').decode("utf-8")
   return str(text)


class MobilenetV2SSD():

    def __init__(self, model_pbtxt, model_pb, object_names, language):
        self.net = cv2.dnn.readNetFromTensorflow(model_pbtxt, model_pb)
        self.classes = []
        self.object_names = object_names
        with open(object_names[language]) as names:
            for line in names:
                self.classes.append(line.strip('\n').decode("utf-8"))
        self.last_visible_objects = {}

    def reload_classes(self, language):
        self.classes = []
        with open(self.object_names[language]) as names:
            for line in names:
                self.classes.append(line.strip('\n').decode("utf-8"))

    def label_image_content(self, imageBGR):
        blob = cv2.dnn.blobFromImage(imageBGR, size=(300, 300), swapRB=False, crop=False)
        self.net.setInput(blob)
        outputs = self.net.forward()
        width = imageBGR.shape[1]
        height = imageBGR.shape[0]
        objects = {}
        for detection in outputs[0,0,:,:]:
            score = float(detection[2])
            if score > 0.3:
                classID = int(detection[1])
                left = int(detection[3] * width)
                top = int(detection[4] * height)
                right = int(detection[5] * width)
                bottom = int(detection[6] * height)
                cv2.rectangle(imageBGR, (left, top), (right, bottom), (23, 230, 210), thickness=2)
                classe = self.classes[classID - 1]
                if classe in objects:
                    objects[classe] += 1
                else:
                    objects[classe] = 1
                text = "{}: {:.4f}".format(strip_accents(classe), score)
                cv2.putText(imageBGR, text, (left, top + 15),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (23, 230, 210), 1)
        self.last_visible_objects = objects
        return imageBGR


class TinyYoloV4():

    def __init__(self, model_cfg, model_weights, object_names, language):
        self.net = cv2.dnn.readNet(model_weights, model_cfg)
        self.classes = []
        self.object_names = object_names
        self.layer_names = self.net.getUnconnectedOutLayers()
        print(self.layer_names)
        self.layer_names = ["yolo_30"]
        with open(object_names[language]) as names:
            for line in names:
                self.classes.append(line.strip('\n').decode("utf-8"))
        self.last_visible_objects = {}

    def reload_classes(language):
        self.classes = []
        with open(self.object_names[language]) as names:
            for line in names:
                self.classes.append(line.strip('\n').decode("utf-8"))

    def label_image_content(self, imageBGR):
        blob = cv2.dnn.blobFromImage(imageBGR, 1/255.0, (416, 416), swapRB=False, crop=False)
        self.net.setInput(blob)
        outputs = self.net.forward(self.layer_names)
        color = (23, 230, 210)
        width = imageBGR.shape[1]
        height = imageBGR.shape[0]
        save_image = True
        objects = {}
        for output in outputs:
            for detection in output:
                scores = detection[5:]
                classID = numpy.argmax(scores)
                confidence = scores[classID]
                if confidence > 0.5:
                    save_image = True
                    #self.logger.info("Class: %s (%s)" % (classID, confidence))
                    box = detection[:4] * numpy.array([width, height, width, height])
                    (centerX, centerY, bwidth, bheight) = box.astype("int")
                    x = int(centerX - (bwidth / 2))
                    y = int(centerY - (bheight / 2))
                    cv2.rectangle(imageBGR, (x, y), (x + bwidth, y + bheight), color, 2)
                    classe = self.classes[classID]
                    if classe in objects:
                        objects[classe] += 1
                    else:
                        objects[classe] = 1
                    text = "{}: {:.4f}".format(strip_accents(classe), confidence)
                    cv2.putText(imageBGR, text, (x, y - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)

        self.last_visible_objects = objects
        return imageBGR
