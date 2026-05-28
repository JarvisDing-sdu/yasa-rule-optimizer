<?php

class VulnerableController
{
    public function commandAction($request, $response): void
    {
        $cmd = $_REQUEST['cmd'];
        system($cmd);
    }

    public function sqlAction($request, $response): void
    {
        $id = $_GET['id'];
        $sql = "SELECT * FROM users WHERE id = " . $id;
        mysqli_query($GLOBALS['db'], $sql);
    }

    public function xssAction($request, $response): void
    {
        $name = $_POST['name'];
        echo $name;
    }

    public function pathTraversalAction($request, $response): void
    {
        $page = $_GET['page'];
        include $page;
    }

    public function ssrfAction($request, $response): void
    {
        $url = $_GET['url'];
        file_get_contents($url);
    }
}
