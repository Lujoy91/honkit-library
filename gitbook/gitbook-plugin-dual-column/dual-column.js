(function () {
  function build(box) {
    if (box.getAttribute("data-ready")) return;
    box.setAttribute("data-ready", "1");

    var bar = document.createElement("div");
    bar.className = "dual-bar";
    var modes = [["both", "對照"], ["src", "只看原文"], ["tgt", "只看翻譯"]];
    var btns = [];

    function setMode(m) {
      box.setAttribute("data-mode", m);
      btns.forEach(function (b) {
        b.classList.toggle("active", b.getAttribute("data-mode") === m);
      });
    }

    modes.forEach(function (p) {
      var b = document.createElement("button");
      b.className = "dual-btn";
      b.type = "button";
      b.setAttribute("data-mode", p[0]);
      b.textContent = p[1];
      b.addEventListener("click", function () { setMode(p[0]); });
      bar.appendChild(b);
      btns.push(b);
    });

    box.parentNode.insertBefore(bar, box);
    setMode("both");
  }

  function init() {
    var list = document.querySelectorAll(".dual");
    for (var i = 0; i < list.length; i++) build(list[i]);
  }

  if (window.gitbook && window.gitbook.events) {
    window.gitbook.events.bind("page.change", init);
  }
  document.addEventListener("DOMContentLoaded", init);
  init();
})();
