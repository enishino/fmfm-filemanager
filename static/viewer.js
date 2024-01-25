// Viewer controller

// Common config
var img_list = [];
var data_container = document.getElementById('data-container');
var start_from = Number(data_container.getAttribute('start_from'));
var spread = Number(data_container.getAttribute('spread'));
var r2l = Number(data_container.getAttribute('r2l'));
var number = Number(data_container.getAttribute('number'));
var pagenum = Number(data_container.getAttribute('pagenum'));
var query = document.getElementById('search_query').value;
var pagecontroller = document.getElementById("pagecontrol");
var pagenumshow = document.getElementById('position');

// Canvas drawing
var canvas = document.getElementById("canvas");
var ctx = canvas.getContext("2d");
var expansion = 3.0; // internal resolution per canvas size

// URL list

//// ---- Image list handling ---- ////
// Image list creation and modification
// Todo: Split interface update and list making
function list_init() {
  spread = document.getElementById("spread").checked; // By default is read from DB
  highlight = document.getElementById("highlight").checked;

  if (spread) {
    pageshift = document.getElementById("pageshift").checked; // By default is false
    document.getElementById("pageshift").disabled = false;
  } else {
    pageshift = false
    document.getElementById("pageshift").disabled = true;
  }

  if (highlight) {
    queue_append = "?query=" + query;
  } else{
    queue_append = "";
  }
  img_list = Array.from(
    Array(pagenum), (v, k) => "/img/" + data_container.getAttribute('number') + "/" + k + queue_append
  )

  // [Start position]
  // [R2L] direction reversing: left page [0 ... 128] right page
  if (r2l) {
    img_list.reverse();
    start_from = img_list.length - 1 - start_from;
  }

  // Shift the page
  if (pageshift && spread) {
      img_list.unshift(null);
  }

  // Fixing position of out of the range and wrong spreading
  start_from = sane_position(start_from);

  // Paging interface tempering
  pagecontroller.step = 1 + Number(spread);
  pagecontroller.max = img_list.length - 1 + (Number(spread) * img_list.length % 2)
}

function sane_position(pos) {
  // Position overflow fix
  if (pos > img_list.length - 1) {
    return img_list.length - 1 - (Number(spread) * img_list.length % 2)
  }

  // Underflow fix
  if (pos <= 0) {
    return 0;
  }

  // "Left" page should be selected when spread
  return pos - (Number(spread) * pos % 2)
}

// Image path handler
var image_handler = (function () {
  var pos = start_from;

  return {
    right: function () {
      pos += 1 + Number(spread)
    },

    left: function () {
      pos -= 1 + Number(spread)
    },

    set_pos: function (abs_pos) {
      if (isNaN(abs_pos)) {
        console.log("Error: " + abs_pos + " is not a number")
      } else {
        pos = parseInt(abs_pos)
      }
    },
    
    path: function () {
      pos = sane_position(pos)
      if (spread) {
        return [img_list[pos], img_list[pos + 1]];
      } else {
        return [img_list[pos], null];
      }
    },

    current: function () {
      return sane_position(pos);
    },
  };
})();

//// ---- Image obtaining ---- ////
// Delay loading
function image_loader(list){
  async function load(src){
    if(src) {
      const img = new Image();
      img.src = src;
      await img.decode();
      return img;

    } else {
      return null;
    }
  }
  // Todo: need to catch (and remove) all 404s
  return Promise.all(list.map(s => load(s)));
}

// Image preloading
async function preload(pos, direction, size=6) {
  if (direction == "right") {
    _list = img_list.slice(pos, pos + size);
  } else {
    _list = img_list.slice(pos - size, pos);
    _list.reverse();
  }
  return await image_loader(_list);
}

//// ---- Drawing  ---- ////
// Drawing to canvas func.
async function draw(src1, src2) {
  // Changes the cursor
  canvas.style.cursor = "wait";

  let img1, img2
  [img1, img2] = await image_loader([src1, src2]);

  if (img1 && img2) {
    // width-first
    w1 = img1.width * (canvas.height / img1.height);
    w2 = img2.width * (canvas.height / img2.height);
    // height-first
    h1 = img1.height * (canvas.width / img1.width);
    h2 = img2.height * (canvas.width / img2.width);

    if (w1 + w2 > canvas.width) {
      // shrink height limited by width
      ratio = canvas.width / (w1+w2);
      height_imgs = canvas.height * ratio;
      img_hpos = (canvas.height - height_imgs) / 2;
      ctx.drawImage(img1, 0,          img_hpos, w1 * ratio, height_imgs);
      ctx.drawImage(img2, w1 * ratio, img_hpos, w2 * ratio, height_imgs);
    } else {
      // shrink width limited by height
      img_wpos = (canvas.width - w1 - w2) / 2;
      ctx.drawImage(img1, img_wpos,      0, w1, canvas.height);
      ctx.drawImage(img2, w1 + img_wpos, 0, w2, canvas.height);
    }

  } else if (img1 || img2) {
    img_single = img1 || img2;
    h_img = img_single.height * (canvas.width / img_single.width);
    w_img = img_single.width * (canvas.height / img_single.height);

    if (w_img > canvas.width) {
      // shrink height limited by width
      ctx.drawImage(img_single, 0, (canvas.height - h_img) / 2, canvas.width, h_img);
    } else {
      // shrink width limited by height
      ctx.drawImage(img_single, (canvas.width - w_img) / 2, 0, w_img, canvas.height);
    }

  } else {
    console.log("No images are found.");
  }

  // Get back the cursor
  canvas.style.cursor = "auto";
}

// Drawing wrapper
// Todo(bug): this drawing a bit exceeds iPad's screen.
function redraw() {
  // Render canvas precisely
  // I've got why this works from https://teratail.com/questions/67020
  c_width  = document.documentElement.clientWidth  - 10;
  c_height = document.documentElement.clientHeight - 10;
  canvas.style.width = c_width + "px";
  canvas.style.height = c_height + "px";
  canvas.width = c_width * expansion;
  canvas.height = c_height * expansion;

  if (canvas.width / canvas.height < 1.4) {
    spread = false; // Turn off spreading ANYWAY
  } else {
    spread = document.getElementById("spread").checked; // By default is read from DB
  }

  // get image path
  let src1, src2;
  [src1, src2] = image_handler.path();
  draw(src1, src2);
}

//// ---- Interfacing ---- ////
// Page moving wrapper
function pagemove(direction, pos=null) {
  if (pos != null) {
    image_handler.set_pos(pos);
  } else {
    if (direction == "right") {
      image_handler.right();
    } else if (direction == "left") {
      image_handler.left();
    }
  }

  // Take current position (set in above code)
  pos = image_handler.current();
  pagecontroller.value = pos;
  if (r2l) {
    pagenumshow.value = img_list.length - pos;
  } else {
    pagenumshow.value = pos+1;
  }
  redraw();

  // Preload
  // REFACT? need to separate semantic of "right" in moving and preloading context
  if (direction == "right" || direction == "both") {
    preload(pos, "right");
  }
  if (direction == "left" || direction == "both") {
    preload(pos, "left");
  }
}

// Click interface
canvas.addEventListener("click", (e) => {
  const rect = canvas.getBoundingClientRect();
  const point = {
    x: e.clientX - rect.left,
    y: e.clientY - rect.top,
  };
  if (canvas.width - point.x * expansion > canvas.width * 0.6) { // 40% Right
    pagemove("left");
  } else if (canvas.width - point.x * expansion < canvas.width * 0.4) { // 40% Left
    pagemove("right");
  }
});

// Keyboard interface
// Todo: use https://developer.mozilla.org/en-US/docs/Web/API/Keyboard/getLayoutMap
function keyboardEvent(event) {
  if (event.type === "keydown") {
    switch(event.code) {
      case "ArrowLeft":
        pagemove("left");
        break;

      case "ArrowRight":
        pagemove("right");
        break;

      case "Escape":
      case "KeyQ":
        history.back();
        break;
    }
  }
}
addEventListener("keydown", keyboardEvent);

// Wheel triggers the page movement.
function wheelEvent(event) {
  if (event.type === "wheel") {
    // The point is that user don't want to reverse the wheel direction!
    // So here the direction is reversed when R2L is on.
    if (r2l) {
      dY = -event.deltaY;
    } else {
      dY = event.deltaY;
    }
    if (dY < 0) {
      pagemove("left");
    } else {
      pagemove("right");
    }
  }
}
addEventListener("wheel", wheelEvent);

//// ---- Initialization ---- ////
// When window size changes the canvas will be changed
window.onresize = redraw;

// Image list preparation
list_init();

// Preload
if (r2l) {
  pagemove("left", pos=start_from)
} else{
  pagemove("right", pos=start_from)
}

// Draw the canvas
redraw();