"""
Flatten a GitHub repository archive (ZIP) into a single text bundle for LLM evaluation.
Uses tempfile for download and extraction; cleans up on success or failure.
"""
from __future__ import annotations

import logging
import os
import re
import tempfile
import zipfile
from pathlib import Path
from typing import Iterable, List, Optional
from urllib.parse import unquote

import requests

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT = 120
MAX_FILE_BYTES = 500 * 1024
MAX_TOTAL_FILES = 50
MAX_TOTAL_BYTES = 500 * 1024

DIR_BLACKLIST = frozenset(
    {
        'node_modules',
        'venv',
        '.venv',
        'env',
        '.env',
        'build',
        'dist',
        'out',
        'target',
        '.git',
        '__pycache__',
        '.pytest_cache',
        '.mypy_cache',
        '.idea',
        '.vscode',
        'coverage',
        'htmlcov',
        '.tox',
        '.next',
        'vendor',
        'bower_components',
        '.gradle',
        '.nuget',
        'packages',
        'Pods',
        'DerivedData',
    }
)

EXT_WHITELIST = frozenset(
    {
        '.py',
        '.js',
        '.mjs',
        '.cjs',
        '.ts',
        '.tsx',
        '.jsx',
        '.java',
        '.cpp',
        '.cc',
        '.cxx',
        '.c',
        '.h',
        '.hpp',
        '.cs',
        '.go',
        '.rs',
        '.rb',
        '.php',
        '.swift',
        '.kt',
        '.kts',
        '.scala',
        '.sql',
        '.json',
        '.yaml',
        '.yml',
        '.html',
        '.htm',
        '.css',
        '.scss',
        '.sass',
        '.less',
        '.vue',
        '.svelte',
        '.md',
        '.xml',
        '.toml',
        '.ini',
        '.cfg',
        '.sh',
        '.bash',
        '.zsh',
        '.ps1',
        '.r',
        '.m',
        '.gradle',
        '.properties',
        '.dockerfile',
        'dockerfile',
        '.tf',
        '.lua',
        '.pl',
        '.pm',
        '.dart',
        '.ex',
        '.exs',
        '.erl',
        '.hs',
        '.lhs',
        '.clj',
        '.cljs',
        '.tex',
        '.bib',
    }
)


def _github_zip_candidates(repo_url: str) -> List[str]:
    """Turn a GitHub HTML URL into possible archive ZIP URLs."""
    raw = (repo_url or '').strip().rstrip('/')
    if not raw:
        return []
    if raw.lower().endswith('.zip'):
        return [raw]

    tree = re.match(
        r'https?://github\.com/([^/]+)/([^/]+)/tree/([^/]+)/?',
        raw,
        re.IGNORECASE,
    )
    if tree:
        org, repo, branch = tree.group(1), tree.group(2), tree.group(3)
        repo = repo.removesuffix('.git')
        return [f'https://github.com/{org}/{repo}/archive/refs/heads/{branch}.zip']

    blob = re.match(
        r'https?://github\.com/([^/]+)/([^/]+)/blob/([^/]+)/',
        raw,
        re.IGNORECASE,
    )
    if blob:
        org, repo, branch = blob.group(1), blob.group(2), blob.group(3)
        repo = repo.removesuffix('.git')
        return [f'https://github.com/{org}/{repo}/archive/refs/heads/{branch}.zip']

    bare = re.match(r'https?://github\.com/([^/]+)/([^/]+?)(?:\.git)?/?$', raw, re.IGNORECASE)
    if not bare:
        return []
    org, repo = bare.group(1), bare.group(2).removesuffix('.git')
    urls = []
    for branch in ('main', 'master'):
        urls.append(f'https://github.com/{org}/{repo}/archive/refs/heads/{branch}.zip')
    return urls


def _path_has_blacklisted_dir(rel: Path) -> bool:
    for part in rel.parts:
        if part in DIR_BLACKLIST or part.lower() in {d.lower() for d in DIR_BLACKLIST}:
            return True
    return False


def _is_safe_zip_member(member: str) -> bool:
    if not member or member.endswith('/'):
        return False
    parts = member.replace('\\', '/').split('/')
    if '..' in parts or any(p.startswith('..') for p in parts):
        return False
    return not Path(member).is_absolute()


class UniversalRepositoryFlattener:
    """
    Download a GitHub repository ZIP to a temp file, read members in memory with filters,
    and emit a directory listing plus ``===== FILE: … =====`` sections for LLM consumption.
    """

    def flatten(self, github_or_zip_url: str) -> str:
        """
        Return a single string: ASCII tree + ``===== FILE: relative/path =====`` sections.
        On failure returns a short diagnostic string (never raises).
        """
        urls = _github_zip_candidates(github_or_zip_url)
        if not urls:
            return (
                f'(No GitHub repository archive could be resolved from URL: '
                f'{github_or_zip_url[:200]!r})'
            )

        zip_fd: Optional[int] = None
        zip_path: Optional[str] = None

        try:
            last_error: Optional[Exception] = None
            download_ok = False
            for url in urls:
                try:
                    with requests.get(url, timeout=REQUEST_TIMEOUT, stream=True) as resp:
                        if resp.status_code != 200:
                            continue
                        zip_fd, zip_path = tempfile.mkstemp(suffix='.zip', prefix='repo_')
                        try:
                            with os.fdopen(zip_fd, 'wb') as handle:
                                zip_fd = None
                                for chunk in resp.iter_content(chunk_size=1024 * 256):
                                    if chunk:
                                        handle.write(chunk)
                            download_ok = True
                            break
                        except Exception:
                            if zip_fd is not None:
                                try:
                                    os.close(zip_fd)
                                except OSError:
                                    pass
                                zip_fd = None
                            if zip_path and os.path.isfile(zip_path):
                                try:
                                    os.unlink(zip_path)
                                except OSError:
                                    pass
                            zip_path = None
                            raise
                except requests.RequestException as exc:
                    last_error = exc
                    logger.warning('ZIP fetch failed for %s: %s', url, exc)

            if not download_ok or not zip_path:
                detail = str(last_error) if last_error else 'HTTP error'
                return f'(Repository archive download failed: {detail})'

            return self._flatten_zip_file(zip_path)
        except Exception as exc:
            logger.exception('UniversalRepositoryFlattener failed: %s', exc)
            return f'(Repository flattening failed: {exc})'
        finally:
            if zip_fd is not None:
                try:
                    os.close(zip_fd)
                except OSError:
                    pass
            if zip_path and os.path.isfile(zip_path):
                try:
                    os.unlink(zip_path)
                except OSError as exc:
                    logger.warning('Could not remove temp zip %s: %s', zip_path, exc)

    def flatten_local_zip(self, zip_path: str) -> str:
        """Flatten a locally uploaded ZIP file into filtered source text."""
        path = Path(zip_path)
        if not path.is_file():
            return f'(Local ZIP not found: {zip_path})'
        try:
            return self._flatten_zip_file(str(path))
        except Exception as exc:
            logger.exception('Local ZIP flatten failed: %s', exc)
            return f'(Local ZIP flatten failed: {exc})'

    def _flatten_zip_file(self, zip_path: str) -> str:
        included_files: List[tuple[str, str]] = []
        current_files = 0
        current_bytes = 0
        truncated = False

        with zipfile.ZipFile(zip_path, 'r') as archive:
            for info in archive.infolist():
                name = info.filename
                if not name or name.endswith('/'):
                    continue
                try:
                    decoded = name.encode('cp437').decode('utf-8')
                except (UnicodeDecodeError, UnicodeEncodeError):
                    decoded = name
                decoded = unquote(decoded)
                if not _is_safe_zip_member(decoded):
                    continue
                parts = decoded.split('/', 1)
                inner = parts[1] if len(parts) > 1 else parts[0]
                rel = Path(inner)
                if _path_has_blacklisted_dir(rel):
                    continue
                suffix = rel.suffix.lower()
                base = rel.name.lower()
                allowed = suffix in EXT_WHITELIST or base in EXT_WHITELIST
                if not allowed:
                    continue
                if info.file_size > MAX_FILE_BYTES:
                    logger.debug('Skipping oversized file %s (%s bytes)', decoded, info.file_size)
                    continue
                try:
                    data = archive.read(info)
                except (zipfile.BadZipFile, RuntimeError, ValueError) as exc:
                    logger.warning('Skipping unreadable zip member %s: %s', decoded, exc)
                    continue
                try:
                    text = data.decode('utf-8')
                except UnicodeDecodeError:
                    try:
                        text = data.decode('latin-1')
                    except UnicodeDecodeError:
                        logger.debug('Skipping binary-looking file %s', decoded)
                        continue
                if '\x00' in text:
                    continue
                text_bytes = len(data)
                next_file_count = current_files + 1
                next_total_bytes = current_bytes + text_bytes
                if next_total_bytes > MAX_TOTAL_BYTES or next_file_count > MAX_TOTAL_FILES:
                    truncated = True
                    break
                included_files.append((str(rel).replace('\\', '/'), text))
                current_files = next_file_count
                current_bytes = next_total_bytes

        if not included_files:
            return '(Repository archive contained no whitelisted source files under size limit.)'

        included_files.sort(key=lambda x: x[0])
        tree_lines = self._build_tree_lines(path for path, _ in included_files)
        blocks: List[str] = ['## Directory tree (filtered)\n', *tree_lines, '\n']
        for rel_path, body in included_files:
            blocks.append(f'===== FILE: {rel_path} =====\n')
            blocks.append(body.rstrip() + '\n\n')
        if truncated:
            blocks.append(
                'WARNING: Repository truncated due to size limits to protect AI context window\n\n'
            )

        return ''.join(blocks).strip()

    def _build_tree_lines(self, paths: Iterable[str]) -> List[str]:
        """Minimal tree from sorted posix paths."""
        paths_list = sorted(set(paths))
        lines: List[str] = []
        for p in paths_list:
            lines.append(f'- {p}')
        return lines
