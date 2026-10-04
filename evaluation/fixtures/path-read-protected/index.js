// Evaluation fixture only. Do not deploy.
const fs = require("node:fs");
const path = require("node:path");

function readReport(reportsDirectory, callerSelectedName) {
  if (!/^[a-z0-9_-]+\.txt$/.test(callerSelectedName)) throw new Error("Invalid report name");
  return fs.readFileSync(path.join(reportsDirectory, callerSelectedName), "utf8");
}

module.exports = { readReport };
