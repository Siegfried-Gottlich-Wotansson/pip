import os
import sys
import textwrap
from os.path import join
from nose.tools import nottest
from nose import SkipTest
from tests.lib import (reset_env, run_pip, assert_all_changes, src_folder,
                       write_file, pyversion, _create_test_package, pip_install_local,
                       _change_test_package_version, path_to_url, find_links)
from tests.lib.local_repos import local_checkout


def test_no_upgrade_unless_requested():
    """
    No upgrade if not specifically requested.

    """
    reset_env()
    run_pip('install', 'INITools==0.1', expect_error=True)
    result = run_pip('install', 'INITools', expect_error=True)
    assert not result.files_created, 'pip install INITools upgraded when it should not have'


def test_upgrade_to_specific_version():
    """
    It does upgrade to specific version requested.

    """
    env = reset_env()
    run_pip('install', 'INITools==0.1', expect_error=True)
    result = run_pip('install', 'INITools==0.2', expect_error=True)
    assert result.files_created, 'pip install with specific version did not upgrade'
    assert env.site_packages/'INITools-0.1-py%s.egg-info' % pyversion in result.files_deleted
    assert env.site_packages/'INITools-0.2-py%s.egg-info' % pyversion in result.files_created


def test_upgrade_if_requested():
    """
    And it does upgrade if requested.

    """
    env = reset_env()
    run_pip('install', 'INITools==0.1', expect_error=True)
    result = run_pip('install', '--upgrade', 'INITools', expect_error=True)
    assert result.files_created, 'pip install --upgrade did not upgrade'
    assert env.site_packages/'INITools-0.1-py%s.egg-info' % pyversion not in result.files_created


def test_upgrade_with_newest_already_installed():
    """
    If the newest version of a package is already installed, the package should
    not be reinstalled and the user should be informed.
    """

    env = reset_env()
    run_pip('install', '-f', find_links, '--no-index', 'simple')
    result =  run_pip('install', '--upgrade', '-f', find_links, '--no-index', 'simple')
    assert not result.files_created, 'simple upgraded when it should not have'
    assert 'already up-to-date' in result.stdout, result.stdout


def test_upgrade_force_reinstall_newest():
    """
    Force reinstallation of a package even if it is already at its newest
    version if --force-reinstall is supplied.
    """

    env = reset_env()
    result = run_pip('install', 'INITools')
    assert env.site_packages/ 'initools' in result.files_created, sorted(result.files_created.keys())
    result2 = run_pip('install', '--upgrade', '--force-reinstall', 'INITools')
    assert result2.files_updated, 'upgrade to INITools 0.3 failed'
    result3 = run_pip('uninstall', 'initools', '-y', expect_error=True)
    assert_all_changes(result, result3, [env.venv/'build', 'cache'])


def test_uninstall_before_upgrade():
    """
    Automatic uninstall-before-upgrade.

    """
    env = reset_env()
    result = run_pip('install', 'INITools==0.2', expect_error=True)
    assert env.site_packages/ 'initools' in result.files_created, sorted(result.files_created.keys())
    result2 = run_pip('install', 'INITools==0.3', expect_error=True)
    assert result2.files_created, 'upgrade to INITools 0.3 failed'
    result3 = run_pip('uninstall', 'initools', '-y', expect_error=True)
    assert_all_changes(result, result3, [env.venv/'build', 'cache'])


def test_uninstall_before_upgrade_from_url():
    """
    Automatic uninstall-before-upgrade from URL.

    """
    env = reset_env()
    result = run_pip('install', 'INITools==0.2', expect_error=True)
    assert env.site_packages/ 'initools' in result.files_created, sorted(result.files_created.keys())
    result2 = run_pip('install', 'http://pypi.python.org/packages/source/I/INITools/INITools-0.3.tar.gz', expect_error=True)
    assert result2.files_created, 'upgrade to INITools 0.3 failed'
    result3 = run_pip('uninstall', 'initools', '-y', expect_error=True)
    assert_all_changes(result, result3, [env.venv/'build', 'cache'])


def test_upgrade_to_same_version_from_url():
    """
    When installing from a URL the same version that is already installed, no
    need to uninstall and reinstall if --upgrade is not specified.

    """
    env = reset_env()
    result = run_pip('install', 'INITools==0.3', expect_error=True)
    assert env.site_packages/ 'initools' in result.files_created, sorted(result.files_created.keys())
    result2 = run_pip('install', 'http://pypi.python.org/packages/source/I/INITools/INITools-0.3.tar.gz', expect_error=True)
    assert not result2.files_updated, 'INITools 0.3 reinstalled same version'
    result3 = run_pip('uninstall', 'initools', '-y', expect_error=True)
    assert_all_changes(result, result3, [env.venv/'build', 'cache'])


def test_upgrade_from_reqs_file():
    """
    Upgrade from a requirements file.

    """
    env = reset_env()
    write_file('test-req.txt', textwrap.dedent("""\
        PyLogo<0.4
        # and something else to test out:
        INITools==0.3
        """))
    install_result = run_pip('install', '-r', env.scratch_path/ 'test-req.txt')
    write_file('test-req.txt', textwrap.dedent("""\
        PyLogo
        # and something else to test out:
        INITools
        """))
    run_pip('install', '--upgrade', '-r', env.scratch_path/ 'test-req.txt')
    uninstall_result = run_pip('uninstall', '-r', env.scratch_path/ 'test-req.txt', '-y')
    assert_all_changes(install_result, uninstall_result, [env.venv/'build', 'cache', env.scratch/'test-req.txt'])


def test_uninstall_rollback():
    """
    Test uninstall-rollback (using test package with a setup.py
    crafted to fail on install).

    """
    env = reset_env()
    result = run_pip('install', '-f', find_links, '--no-index', 'broken==0.1')
    assert env.site_packages / 'broken.py' in result.files_created, list(result.files_created.keys())
    result2 = run_pip('install', '-f', find_links, '--no-index', 'broken==0.2broken', expect_error=True)
    assert result2.returncode == 1, str(result2)
    assert env.run('python', '-c', "import broken; print(broken.VERSION)").stdout == '0.1\n'
    assert_all_changes(result.files_after, result2, [env.venv/'build', 'pip-log.txt'])

# Issue #530 - temporarily disable flaky test
@nottest
def test_editable_git_upgrade():
    """
    Test installing an editable git package from a repository, upgrading the repository,
    installing again, and check it gets the newer version
    """
    env = reset_env()
    version_pkg_path = _create_test_package(env)
    run_pip('install', '-e', '%s#egg=version_pkg' % ('git+file://' + version_pkg_path))
    version = env.run('version_pkg')
    assert '0.1' in version.stdout
    _change_test_package_version(env, version_pkg_path)
    run_pip('install', '-e', '%s#egg=version_pkg' % ('git+file://' + version_pkg_path))
    version2 = env.run('version_pkg')
    assert 'some different version' in version2.stdout, "Output: %s" % (version2.stdout)


def test_should_not_install_always_from_cache():
    """
    If there is an old cached package, pip should download the newer version
    Related to issue #175
    """
    env = reset_env()
    run_pip('install', 'INITools==0.2', expect_error=True)
    run_pip('uninstall', '-y', 'INITools')
    result = run_pip('install', 'INITools==0.1', expect_error=True)
    assert env.site_packages/'INITools-0.2-py%s.egg-info' % pyversion not in result.files_created
    assert env.site_packages/'INITools-0.1-py%s.egg-info' % pyversion in result.files_created


def test_install_with_ignoreinstalled_requested():
    """
    It installs package if ignore installed is set.

    """
    env = reset_env()
    run_pip('install', 'INITools==0.1', expect_error=True)
    result = run_pip('install', '-I', 'INITools', expect_error=True)
    assert result.files_created, 'pip install -I did not install'
    assert env.site_packages/'INITools-0.1-py%s.egg-info' % pyversion not in result.files_created


def test_upgrade_vcs_req_with_no_dists_found():
    """It can upgrade a VCS requirement that has no distributions otherwise."""
    reset_env()
    req = "%s#egg=pip-test-package" % local_checkout(
        "git+http://github.com/pypa/pip-test-package.git")
    run_pip("install", req)
    result = run_pip("install", "-U", req)
    assert not result.returncode


def test_upgrade_vcs_req_with_dist_found():
    """It can upgrade a VCS requirement that has distributions on the index."""
    reset_env()
    # TODO(pnasrat) Using local_checkout fails on windows - oddness with the test path urls/git.
    req = "%s#egg=virtualenv" % "git+git://github.com/pypa/virtualenv@c21fef2c2d53cf19f49bcc37f9c058a33fb50499"
    run_pip("install", req)
    result = run_pip("install", "-U", req)
    assert not "pypi.python.org" in result.stdout, result.stdout


class TestUpgradeSetuptools(object):
    """
    Tests for upgrading to setuptools (using pip from src tree)
    The tests use a *fixed* set of packages from our test packages dir
    note: virtualenv-1.9.1 contains distribute-0.6.34
    note: virtualenv-1.10 contains setuptools-0.9.7
    """

    def prep_ve(self, version, distribute=False):
        self.env = reset_env(pypi_cache=False)
        pip_install_local('virtualenv==%s' %version)
        args = ['virtualenv', self.env.scratch_path/'VE']
        if distribute:
            args.insert(1, '--distribute')
        self.env.run(*args)
        self.ve_bin = self.env.scratch_path/'VE'/'bin'
        self.env.run(self.ve_bin/'pip', 'uninstall', '-y', 'pip')
        self.env.run(self.ve_bin/'python', 'setup.py', 'install', cwd=src_folder, expect_stderr=True)

    def test_py2_from_setuptools_6_to_setuptools_7(self):
        if sys.version_info >= (3,):
            raise SkipTest()
        self.prep_ve('1.9.1')
        result = self.env.run(self.ve_bin/'pip', 'install', '--no-index', '--find-links=%s' % find_links, '-U', 'setuptools')
        assert "Found existing installation: setuptools 0.6c11" in result.stdout
        result = self.env.run(self.ve_bin/'pip', 'list')
        "setuptools (0.9.8)" in result.stdout

    def test_py2_py3_from_distribute_6_to_setuptools_7(self):
        self.prep_ve('1.9.1', distribute=True)
        result = self.env.run(self.ve_bin/'pip', 'install', '--no-index', '--find-links=%s' % find_links, '-U', 'setuptools')
        assert "Found existing installation: distribute 0.6.34" in result.stdout
        result = self.env.run(self.ve_bin/'pip', 'list')
        "setuptools (0.9.8)" in result.stdout
        "distribute (0.7.3)" in result.stdout

    def test_from_setuptools_7_to_setuptools_7(self):
        self.prep_ve('1.10')
        result = self.env.run(self.ve_bin/'pip', 'install', '--no-index', '--find-links=%s' % find_links, '-U', 'setuptools')
        assert "Found existing installation: setuptools 0.9.7" in result.stdout
        result = self.env.run(self.ve_bin/'pip', 'list')
        "setuptools (0.9.8)" in result.stdout

    def test_from_setuptools_7_to_setuptools_7_using_wheel(self):
        self.prep_ve('1.10')
        result = self.env.run(self.ve_bin/'pip', 'install', '--use-wheel', '--no-index', '--find-links=%s' % find_links, '-U', 'setuptools')
        assert "Found existing installation: setuptools 0.9.7" in result.stdout
        assert 'setuptools-0.9.8.dist-info' in str(result.files_created) #only wheels use dist-info
        result = self.env.run(self.ve_bin/'pip', 'list')
        "setuptools (0.9.8)" in result.stdout

    def test_from_setuptools_7_to_setuptools_7_with_distribute_7_installed(self):
        self.prep_ve('1.9.1', distribute=True)
        result = self.env.run(self.ve_bin/'pip', 'install', '--no-index', '--find-links=%s' % find_links, '-U', 'setuptools')
        result = self.env.run(self.ve_bin/'pip', 'install', '--no-index', '--find-links=%s' % find_links, 'setuptools==0.9.6')
        result = self.env.run(self.ve_bin/'pip', 'list')
        "setuptools (0.9.6)" in result.stdout
        "distribute (0.7.3)" in result.stdout
        result = self.env.run(self.ve_bin/'pip', 'install', '--no-index', '--find-links=%s' % find_links, '-U', 'setuptools')
        assert "Found existing installation: setuptools 0.9.6" in result.stdout
        result = self.env.run(self.ve_bin/'pip', 'list')
        "setuptools (0.9.8)" in result.stdout
        "distribute (0.7.3)" in result.stdout
