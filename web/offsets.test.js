/* node web/offsets.test.js */
var fs = require("fs");
var path = require("path");
var src = fs.readFileSync(path.join(__dirname, "offsets.js"), "utf8");
eval(src);

var offsets = globalThis.SKEPTID_OFFSETS;
var failed = 0;

function assert(name, cond) {
  if (!cond) {
    failed += 1;
    console.error("FAIL " + name);
  } else {
    console.log("ok   " + name);
  }
}

var emojiText = "hi 😀 there";
assert("emoji is one code point", offsets.unitsOf(emojiText)[3] === "😀");
assert("utf16 slice of emoji is broken", emojiText.slice(3, 4) !== "😀");

var range = offsets.utf16RangeFromCodePoints(emojiText, 3, 4);
assert("code-point slice yields the emoji", range && range.excerpt === "😀");
assert("utf16 start skips the surrogate pair", range.start === 3 && emojiText.slice(range.start, range.end) === "😀");

var found = offsets.findCodePointSpan(emojiText, "😀");
assert("find emoji span", found && found.start === 3 && found.end === 4);

var flagged = offsets.sliceCodePoints("pay 😀 now", 4, 5);
assert("sliceCodePoints emoji", flagged === "😀");

if (failed) {
  process.exit(1);
}
console.log("all offsets tests passed");
