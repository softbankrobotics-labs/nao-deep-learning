
var img;
var preloadImage = new Image();
preloadImage.onload = function() {
  document.getElementById("img").src = preloadImage.src;
}

function updateImageSrc() {
  let dt = new Date();
  let baseUrl = "img/deep.jpg";
  img = baseUrl + "?t=" + dt.getTime();
  preloadImage.src = img;
}

setInterval(updateImageSrc, 300);

function setImageClickListener() {
  document.querySelector('#img').onclick = function (e) {
    var rect = e.target.getBoundingClientRect();
    var x = (e.clientX - rect.left) / (rect.width / 2) - 1; //x position within the element.
    var y = -((e.clientY - rect.top) / (rect.height / 2) - 1);  //y position within the element.
    DeepNaoService.webLookAt(x, y);
    console.log(x);
    console.log(y);
  }
}

var DeepNaoService = null;

function setContinuousDescritionCheckboxClickListener() {
  const checkbox = document.getElementById('continuous_description_checkbox')
  checkbox.addEventListener('change', (event) => {
    if (event.currentTarget.checked) {
      DeepNaoService.continuous_description.setValue(true);
    } else {
      DeepNaoService.continuous_description.setValue(false);
    }
    console.log("Checkbox checked: " + event.currentTarget.checked);
  });
}

function setContinuousExplorationCheckboxClickListener() {
  const checkbox = document.getElementById('continuous_exploration_checkbox')
  checkbox.addEventListener('change', (event) => {
    if (event.currentTarget.checked) {
      DeepNaoService.continuous_exploration.setValue(true);
    } else {
      DeepNaoService.continuous_exploration.setValue(false);
    }
    console.log("Checkbox checked: " + event.currentTarget.checked);
  });
}

function setCustomModelCheckboxClickListener() {
  const checkbox = document.getElementById('use_custom_model_checkbox')
  checkbox.addEventListener('change', (event) => {
    if (event.currentTarget.checked) {
      DeepNaoService.use_custom_model.setValue(true);
    } else {
      DeepNaoService.use_custom_model.setValue(false);
    }
    console.log("Checkbox checked: " + event.currentTarget.checked);
  });
}

function setDescribeButtonClickListener() {
  document.getElementById("describe").addEventListener("click", function() {
    DeepNaoService.describeVisibleObjects();
  });
}

function onContinuousDescriptionChange(value) {
  const checkbox = document.getElementById('continuous_description_checkbox')
  checkbox.checked = value;
  console.log("Checkbox checked: " + value);
}

function onContinuousExplorationChange(value) {
  const checkbox = document.getElementById('continuous_exploration_checkbox')
  checkbox.checked = value;
  console.log("Checkbox checked: " + value);
}

function onUseCustomModelChange(value) {
  const checkbox = document.getElementById('use_custom_model_checkbox')
  checkbox.checked = value;
  console.log("Checkbox checked: " + value);
}

function onCustomModelAvailable(value) {
  if (value) {
    document.getElementById('use_custom_model_line').style.display = "flex";
  }
}

function onDeepNaoRunningChange(isRunning) {
  if (isRunning) {
    document.getElementById('main').style.display = "flex";
    document.getElementById('not_running').style.display = "none";
  } else {
    document.getElementById('main').style.display = "none";
    document.getElementById('not_running').style.display = "block";
  }
}

function onLanguageChange(value) {
  console.log("onLanguageChange: " + value)
  if ((value == "French") || (value == "fr_FR")) {
    document.getElementById('describe').textContent = "Décris ce que tu vois";
    document.getElementById('continuous_describe_label').textContent = "Décris en continue:";
    document.getElementById('continuous_explore_label').textContent = "Explore en continue:";
    document.getElementById('use_custom_model_label').textContent = "Utilise un modèle personnalisé:";
    document.getElementById('not_running').textContent = "Le service DeepNao n'est pas actif. Veuillez mettre NAO debout ou assis puis double cliquer sur le bouton torse de NAO.";
  } else {
    document.getElementById('describe').textContent = "Describe what you see";
    document.getElementById('continuous_describe_label').textContent = "Describe continuously:";
    document.getElementById('continuous_explore_label').textContent = "Explore continuously:";
    document.getElementById('use_custom_model_label').textContent = "Use custom model:";
    document.getElementById('not_running').textContent = "DeepNao service is not running. Please sit or stand NAO then double click on NAO chest button.";
  }
}

RobotUtils.onService(function(DeepNao) {
  console.log("Service DeepNao available");
  DeepNaoService = DeepNao;
  setImageClickListener();
  setContinuousDescritionCheckboxClickListener();
  setContinuousExplorationCheckboxClickListener();
  setCustomModelCheckboxClickListener();
  setDescribeButtonClickListener();
  DeepNao.continuous_description.value().then(onContinuousDescriptionChange);
  DeepNao.continuous_exploration.value().then(onContinuousExplorationChange);
  DeepNao.use_custom_model.value().then(onUseCustomModelChange);
  DeepNao.use_custom_model.connect(onUseCustomModelChange);
  DeepNao.isCustomModelAvailable().then(onCustomModelAvailable);
  DeepNao.running.value().then(onDeepNaoRunningChange);
  DeepNao.running.connect(onDeepNaoRunningChange);
});

RobotUtils.onService(function(ALTextToSpeech) {
  console.log("Service ALTextToSpeech available");
  ALTextToSpeech.getLanguage().then(onLanguageChange);
  ALTextToSpeech.languageTTS.connect(onLanguageChange);
});
