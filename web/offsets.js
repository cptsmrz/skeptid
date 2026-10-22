/* Unicode code-point offsets. Backend start/end count code points, not UTF-16. */
(function (root) {
  "use strict";

  function unitsOf(text) {
    return Array.from(text == null ? "" : String(text));
  }

  function sliceCodePoints(text, start, end) {
    var units = unitsOf(text);
    var a = Math.max(0, start | 0);
    var b = end == null ? units.length : Math.max(a, end | 0);
    return units.slice(a, b).join("");
  }

  function utf16RangeFromCodePoints(text, start, end) {
    var units = unitsOf(text);
    var len = units.length;
    if (typeof start !== "number" || typeof end !== "number") return null;
    if (start < 0 || end > len || start >= end) return null;
    var before = units.slice(0, start).join("");
    var excerpt = units.slice(start, end).join("");
    return {
      start: before.length,
      end: before.length + excerpt.length,
      excerpt: excerpt
    };
  }

  function findCodePointSpan(text, needle) {
    if (!needle) return null;
    var units = unitsOf(text);
    var n = unitsOf(needle);
    if (!n.length || n.length > units.length) return null;
    for (var i = 0; i <= units.length - n.length; i++) {
      var match = true;
      for (var j = 0; j < n.length; j++) {
        if (units[i + j] !== n[j]) {
          match = false;
          break;
        }
      }
      if (match) return { start: i, end: i + n.length };
    }
    return null;
  }

  root.SKEPTID_OFFSETS = {
    unitsOf: unitsOf,
    sliceCodePoints: sliceCodePoints,
    utf16RangeFromCodePoints: utf16RangeFromCodePoints,
    findCodePointSpan: findCodePointSpan
  };
})(typeof window !== "undefined" ? window : globalThis);
