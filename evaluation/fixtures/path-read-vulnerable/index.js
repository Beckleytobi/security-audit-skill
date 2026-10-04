// Evaluation fixture only. Do not deploy.
const fs = require("node:fs");
const path = require("node:path");

function readReport(reportsDirectory, callerSelectedName) {
  return fs.readFileSync(path.resolve(reportsDirectory, callerSelectedName), "utf8");
}

module.exports = { readReport };
