

function _arrayBufferToBase64(bytes) {
    var binary = '';
    var len = bytes.byteLength;
    for (var i = 0; i < len; i++) {
        binary += String.fromCharCode( bytes[ i ] );
    }
    return window.btoa( binary );
}

function parseFile(file, callback) {
  return new Promise(function (resolve, reject) {
    var fileSize   = file.size;
    var chunkSize  = 64 * 1024; // bytes
    var offset     = 0;
    var self       = this; // we need a reference to the current object
    var chunkReaderBlock = null;

    var readEventHandler = function(evt) {
      if (evt.target.error == null) {
        var bytes = new Uint8Array(evt.target.result)
        console.log(bytes.byteLength);
        callback(_arrayBufferToBase64(bytes), offset); // callback for handling read chunk
        offset += bytes.byteLength;
      } else {
        console.log("Read error: " + evt.target.error);
        reject();
        return;
      }
      if (offset >= fileSize) {
        resolve(fileSize);
        console.log("Done reading file");
        return;
      }

      // of to the next chunk
      chunkReaderBlock(offset, chunkSize, file);
    }

    chunkReaderBlock = function(_offset, length, _file) {
      var r = new FileReader();
      var blob = _file.slice(_offset, length + _offset);
      r.onload = readEventHandler;
      r.readAsArrayBuffer(blob);
    }

    // now let's start the read with the first block
    chunkReaderBlock(offset, chunkSize, file);
  });
}

var DeepNaoService = null;

function uploadFile(file_type, input_id) {
  console.log("Upload file")
  return new Promise(function (resolve, reject) {
    DeepNaoService.startUpload(file_type);
    parseFile(document.getElementById(input_id).files[0], function(chunk, offset) {
      DeepNaoService.uploadChunk(chunk, offset, file_type);
    }).then(function (size) {
      DeepNaoService.finishUpload(size, file_type).then(function () {
        resolve();
      })
    }, function (error) {
      reject(error);
    });
  });

}

function displayLoading() {
  document.getElementById("blackout").style.display = "block";
}

function hideLoading() {
  document.getElementById("blackout").style.display = "none";
  document.getElementById("loadingicon").style.borderColor = "white";
}

function uploadError(e) {
  alert("Error uploading file");
  hideLoading();
}

function upload() {
  color = "#0176d3";
  displayLoading();
  document.getElementById("loadingicon").style.borderLeftColor = color;
  uploadFile("weights", 'weights-input').then(function () {
    document.getElementById("loadingicon").style.borderTopColor = color;
    uploadFile("config", 'config-input').then(function () {
      document.getElementById("loadingicon").style.borderRightColor = color;
      uploadFile("names_fr", 'names-fr-input').then(function () {
        document.getElementById("loadingicon").style.borderBottomColor = color;
        uploadFile("names_en", 'names-en-input').then(function () {
          hideLoading();
          window.location.href = "index.html"
        }, uploadError);
      }, uploadError);
    }, uploadError);
  }, uploadError);
}

function enableUpload() {
  document.getElementById('upload').disabled = !Boolean(
    document.getElementById('config-input').value &&
      document.getElementById('weights-input').value &&
      document.getElementById('names-fr-input').value &&
      document.getElementById('names-en-input').value
  );
}

document.getElementById('config-input').addEventListener('change', enableUpload, false);
document.getElementById('weights-input').addEventListener('change', enableUpload, false);
document.getElementById('names-fr-input').addEventListener('change', enableUpload, false);
document.getElementById('names-en-input').addEventListener('change', enableUpload, false);


function setUploadClickListener() {
  document.querySelector('#upload').onclick = function (e) {
    upload();
  }
}

function onLanguageChange(value) {
  console.log("onLanguageChange: " + value)
  if ((value == "French") || (value == "fr_FR")) {
    document.getElementById('title').textContent = "Télécharger un modèle personnalisé";
    document.getElementById('config-input-label').textContent
      = "Fichier de configuration du modèle (model.cfg)";
    document.getElementById('weight-input-label').textContent
      = "Fichier de poids du modèle (model.weights)";
    document.getElementById('names-fr-input-label').textContent
      = "Noms des objets en Francais (objects.names.fr)";
    document.getElementById('names-en-input-label').textContent
      = "Noms des objets en Anglais (objects.names.en)";
    document.getElementById('upload').textContent = "Télécharger les fichiers";
    document.getElementById('loadingtext').textContent = "Téléchargement...";
  } else {
    document.getElementById('title').textContent = "Upload a custom model";
    document.getElementById('config-input-label').textContent
      = "Model config file (model.cfg):";
    document.getElementById('weight-input-label').textContent
      = "Model weight file (model.weights):";
    document.getElementById('names-fr-input-label').textContent
      = "Objects names in French (objects.names.fr):";
    document.getElementById('names-en-input-label').textContent
      = "Objects names in English (objects.names.en):";
    document.getElementById('upload').textContent = "Upload files";
    document.getElementById('loadingtext').textContent = "Uploading...";
  }
}

RobotUtils.onService(function(DeepNao) {
  document.getElementById('main').style.display = "flex";
  console.log("Service DeepNao available");
  DeepNaoService = DeepNao;
  setUploadClickListener();
});

RobotUtils.onService(function(ALTextToSpeech) {
  console.log("Service ALTextToSpeech available");
  ALTextToSpeech.getLanguage().then(onLanguageChange);
  ALTextToSpeech.languageTTS.connect(onLanguageChange);
});
