import os
import sqlite3
import subprocess


def command_injection_case():
    cmd = input("cmd: ")
    os.system(cmd)


def subprocess_case():
    cmd = input("subprocess cmd: ")
    subprocess.run(cmd, shell=True)


def code_execution_case():
    expression = input("expr: ")
    eval(expression)


def sql_injection_case():
    user_id = input("id: ")
    sql = "SELECT * FROM users WHERE id = " + user_id
    cursor = sqlite3.connect(":memory:").cursor()
    cursor.execute(sql)


if __name__ == "__main__":
    command_injection_case()
    subprocess_case()
    code_execution_case()
    sql_injection_case()
