<?xml version="1.0" encoding="UTF-8" ?>
<Package name="deep_nao" format_version="5">
    <Manifest src="manifest.xml" />
    <BehaviorDescriptions>
      <BehaviorDescription name="behavior" src="behavior" xar="behavior.xar" />
    </BehaviorDescriptions>
    <Dialogs />
    <Resources>
      <File name="deep_nao" src="scripts/deep_nao.py" />
      <File name="deep_nao" src="scripts/stop_behavior.py" />
      <File name="models" src="scripts/models.py" />
      <File name="translations" src="scripts/translations.py" />
      <File name="deep_nao" src="scripts/explorer.py" />
      <File name="worker" src="scripts/stk/worker.py" />
      <File name="logging" src="scripts/stk/logging.py" />
      <File name="services" src="scripts/stk/services.py" />
      <File name="__init__" src="scripts/stk/__init__.py" />
      <File name="runner" src="scripts/stk/runner.py" />
      <File name="events" src="scripts/stk/events.py" />

      <File name="dialog" src="dialog/dialog-en.top" />

      <File name="cv2.so" src="lib/python2.7/site-packages/cv2.so" />

      <File name="yolo_v4_tiny_custom_folder" src="models/yolo_v4_tiny_custom/.empty" />

      <File name="ssd_mobilenet_v2_oid_v4_names" src="models/ssd_mobilenet_v2_oid_v4/objects.names.en" />
      <File name="ssd_mobilenet_v2_oid_v4_names" src="models/ssd_mobilenet_v2_oid_v4/objects.names.fr" />
      <File name="ssd_mobilenet_v2_oid_v4_pbtxt" src="models/ssd_mobilenet_v2_oid_v4/graph.pbtxt" />
      <File name="ssd_mobilenet_v2_oid_v4_pb" src="models/ssd_mobilenet_v2_oid_v4/frozen_inference_graph.pb" />

      <File name="index" src="html/index.html" />
      <File name="index" src="html/upload.html" />
      <File name="index" src="html/upload.js" />
      <File name="img" src="html/img/.empty" />
      <File name="indexjs" src="html/index.js" />
      <File name="robotutils" src="html/robotutils.js" />
      <File name="style" src="html/style.css" />
      <File name="deep" src="html/img/deep.jpg" />

    </Resources>
    <Topics>
    </Topics>
    <IgnoredPaths>
        <Path src=".metadata" />
    </IgnoredPaths>
    <Translations auto-fill="en_US">
    </Translations>
</Package>
