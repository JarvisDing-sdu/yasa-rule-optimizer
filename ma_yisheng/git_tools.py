"""
Git repository analysis tools for the MaYisheng Agent.
Clone repos, view commit history, and inspect diffs.
"""
import os
import subprocess
import tempfile
import shutil

GIT_CLONE_DIR = "/tmp/ma_yisheng_git"


def _ensure_clone_dir():
    os.makedirs(GIT_CLONE_DIR, exist_ok=True)


def tool_git_clone(repo_url: str) -> str:
    """
    Clone a Git repository for analysis. Useful when you find a PoC or security project on GitHub.
    repo_url: Git clone URL (e.g. https://github.com/user/repo.git or https://github.com/user/repo)
    Returns the local path of the cloned repo.
    """
    _ensure_clone_dir()
    if not repo_url.startswith("http"):
        return "错误：请提供完整的 GitHub/GitLab 仓库 URL"

    repo_name = repo_url.rstrip("/").split("/")[-1].replace(".git", "")
    target = os.path.join(GIT_CLONE_DIR, repo_name)

    # Remove if already exists
    if os.path.exists(target):
        shutil.rmtree(target)

    try:
        result = subprocess.run(
            ["git", "clone", "--depth", "50", repo_url, target],
            capture_output=True, text=True, timeout=60,
        )
        if result.returncode != 0:
            return f"克隆失败: {result.stderr[:500]}"
        # Show basic info
        size = _dir_size(target)
        files = len(os.listdir(target))
        return f"已克隆到 {target}\n仓库大小: {size:.1f}MB, 顶层 {files} 个文件/目录\n\n{result.stderr[-300:] if result.stderr else ''}"
    except subprocess.TimeoutExpired:
        return "克隆超时（60秒），仓库可能太大"
    except FileNotFoundError:
        return "错误：系统未安装 git"
    except Exception as e:
        return f"克隆失败: {str(e)}"


def tool_git_log(repo_path: str, max_count: int = 10) -> str:
    """
    View recent commit history of a cloned repository.
    repo_path: Local path to the cloned repo
    max_count: Number of recent commits to show (default 10)
    """
    if not os.path.isdir(repo_path):
        return f"错误：路径 {repo_path} 不存在，请先用 git_clone 克隆仓库"

    try:
        result = subprocess.run(
            ["git", "-C", repo_path, "log", f"--max-count={max_count}",
             "--oneline", "--no-decorate"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode != 0:
            return f"获取提交历史失败: {result.stderr[:300]}"
        if not result.stdout.strip():
            return "仓库无提交记录"
        return f"## {os.path.basename(repo_path)} 最近 {max_count} 次提交\n\n{result.stdout}"
    except Exception as e:
        return f"获取提交历史失败: {str(e)}"


def tool_git_show(repo_path: str, commit: str) -> str:
    """
    Show the full diff of a specific commit. Use to understand what changed and find vulnerabilities.
    repo_path: Local path to the cloned repo
    commit: Commit hash (full or short) to inspect
    Returns the unified diff.
    """
    if not os.path.isdir(repo_path):
        return f"错误：路径 {repo_path} 不存在"

    try:
        # Get commit message + stats
        stat_result = subprocess.run(
            ["git", "-C", repo_path, "show", "--stat", "--format=%H %s%n%n%b", commit],
            capture_output=True, text=True, timeout=15,
        )
        if stat_result.returncode != 0:
            return f"获取提交信息失败: {stat_result.stderr[:300]}"

        # Get the diff (truncate if too large)
        diff_result = subprocess.run(
            ["git", "-C", repo_path, "diff", f"{commit}~1..{commit}"],
            capture_output=True, text=True, timeout=15,
        )
        diff_text = diff_result.stdout
        if len(diff_text) > 8000:
            diff_text = diff_text[:8000] + "\n\n... [diff 被截断，共 " + str(len(diff_result.stdout)) + " 字符]"

        return f"## 提交详情\n\n{stat_result.stdout[:1000]}\n\n## Diff\n\n```diff\n{diff_text}\n```"
    except Exception as e:
        return f"获取 diff 失败: {str(e)}"


def tool_git_diff(repo_path: str, commit1: str = "HEAD~1", commit2: str = "HEAD") -> str:
    """
    Compare two commits or branches. Useful for reviewing code changes between versions.
    repo_path: Local path to the cloned repo
    commit1: Older commit/branch/tag (default: HEAD~1)
    commit2: Newer commit/branch/tag (default: HEAD)
    Returns the unified diff.
    """
    if not os.path.isdir(repo_path):
        return f"错误：路径 {repo_path} 不存在"

    try:
        result = subprocess.run(
            ["git", "-C", repo_path, "diff", "--stat", commit1, commit2],
            capture_output=True, text=True, timeout=15,
        )
        if result.returncode != 0:
            return f"比较失败: {result.stderr[:300]}"

        diff_result = subprocess.run(
            ["git", "-C", repo_path, "diff", commit1, commit2],
            capture_output=True, text=True, timeout=30,
        )
        diff_text = diff_result.stdout
        if len(diff_text) > 10000:
            diff_text = diff_text[:10000] + "\n\n... [diff 被截断]"

        return f"## {commit1} → {commit2}\n\n### 文件变更\n{result.stdout}\n\n### Diff\n```diff\n{diff_text}\n```"
    except Exception as e:
        return f"比较失败: {str(e)}"


def tool_git_list_files(repo_path: str, path: str = "") -> str:
    """
    List files in a cloned repository. Use to explore the project structure.
    repo_path: Local path to the cloned repo
    path: Subdirectory to list (default: root)
    """
    if not os.path.isdir(repo_path):
        return f"错误：路径 {repo_path} 不存在"

    target = os.path.join(repo_path, path)
    if not os.path.isdir(target):
        return f"错误：{path} 不是有效目录"

    try:
        files = sorted(os.listdir(target))
        lines = [f"## {os.path.basename(repo_path)}/{path}" if path else f"## {os.path.basename(repo_path)} 根目录"]
        lines.append("")
        for f in files[:50]:
            full = os.path.join(target, f)
            prefix = "📁" if os.path.isdir(full) else "📄"
            size = ""
            if os.path.isfile(full):
                s = os.path.getsize(full)
                size = f" ({_fmt_size(s)})"
            lines.append(f"{prefix} {f}{size}")
        if len(files) > 50:
            lines.append(f"... 还有 {len(files) - 50} 个文件")
        return "\n".join(lines)
    except Exception as e:
        return f"列出文件失败: {str(e)}"


def _dir_size(path: str) -> float:
    total = 0
    for dirpath, dirnames, filenames in os.walk(path):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            try:
                total += os.path.getsize(fp)
            except OSError:
                pass
    return total / (1024 * 1024)


def _fmt_size(size: int) -> str:
    if size < 1024:
        return f"{size}B"
    elif size < 1024 * 1024:
        return f"{size / 1024:.1f}KB"
    else:
        return f"{size / (1024 * 1024):.1f}MB"
