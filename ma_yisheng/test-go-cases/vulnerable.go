package main

import (
	"database/sql"
	"net/http"
	"os"
	"os/exec"
)

func commandInjectionCase(r *http.Request) {
	cmd := r.FormValue("cmd")
	exec.Command(cmd).Run()
}

func sqlInjectionCase(r *http.Request, db *sql.DB) {
	id := r.FormValue("id")
	query := "SELECT * FROM users WHERE id = " + id
	db.Query(query)
}

func pathTraversalCase(r *http.Request) {
	fileName := r.FormValue("file")
	os.Create(fileName)
}

func ssrfCase(r *http.Request) {
	url := r.FormValue("url")
	http.Get(url)
}

func main() {
	var r *http.Request
	var db *sql.DB

	commandInjectionCase(r)
	sqlInjectionCase(r, db)
	pathTraversalCase(r)
	ssrfCase(r)
}
