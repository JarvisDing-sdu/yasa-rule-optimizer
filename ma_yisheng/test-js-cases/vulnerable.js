const child_process = require('child_process');
const fs = require('fs');
const axios = require('axios');

function commandInjectionCase(req, res) {
  const cmd = req.query.cmd;
  child_process.exec(cmd);
  res.send(cmd);
}

function sqlInjectionCase(req, connection) {
  const id = req.query.id;
  const sql = 'SELECT * FROM users WHERE id = ' + id;
  connection.query(sql);
}

function pathTraversalCase(req) {
  const fileName = req.query.file;
  fs.readFileSync(fileName);
}

function ssrfCase(req) {
  const url = req.query.url;
  axios.get(url);
}

module.exports = {
  commandInjectionCase,
  sqlInjectionCase,
  pathTraversalCase,
  ssrfCase,
};
