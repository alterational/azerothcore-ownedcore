"""Text-level guards for the Windows workflow's dependency and release pins.

The workflow is the only place where the Boost/MySQL versions, the
`RelWithDebInfo` build type, the four-DLL staging step, and the single-ZIP
publication are wired together. These tests keep those invariants from drifting
back to the older Boost 1.87 / MySQL 8.4.9 / `bin/` + `etc/` / nested-ZIP setup.

They are skipped when PyYAML is unavailable so the Ubuntu validation job does not
gain a new runtime dependency.
"""
from __future__ import annotations

import unittest
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover - exercised only when PyYAML is absent
    yaml = None

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = ROOT / ".github" / "workflows" / "windows-release.yml"


def load_workflow() -> dict:
    return yaml.safe_load(WORKFLOW_PATH.read_text(encoding="utf-8"))


def step(workflow: dict, job: str, name: str) -> dict:
    for candidate in workflow["jobs"][job]["steps"]:
        if candidate.get("name") == name:
            return candidate
    raise AssertionError(f"Step {name!r} not found in job {job!r}")


@unittest.skipIf(yaml is None, "PyYAML is not installed")
class WindowsWorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.workflow = load_workflow()
        self.text = WORKFLOW_PATH.read_text(encoding="utf-8")

    def test_dependencies_are_exactly_boost_192_mysql_8411(self) -> None:
        build = self.workflow["jobs"]["build"]
        self.assertEqual(build["env"]["BOOST_ROOT"], r"C:\local\boost_1_92_0")

        cache = step(self.workflow, "build", "Cache Boost and MySQL client")
        self.assertEqual(cache["with"]["key"], "winbuild-deps-boost-1.92.0-msvc14.3-mysql-8.4.11")
        self.assertNotIn("restore-keys", cache["with"])
        self.assertIn(r"C:\local\boost_1_92_0", cache["with"]["path"])
        self.assertIn(r"C:\tools\mysql\current", cache["with"]["path"])

        dependencies = step(self.workflow, "build", "Configure Windows dependencies")["run"]
        self.assertIn("$boostVersion = '1.92.0'", dependencies)
        self.assertIn("https://archives.boost.io/release/$boostVersion/binaries/$boostFileName", dependencies)
        self.assertIn("boost_1_92_0-msvc-14.3-64.exe", dependencies)
        self.assertIn("90db7bdf26ad34a670fcf5b43c95c5253252098de01402cd758df8e801c383b3", dependencies)
        self.assertIn("Get-FileHash -Algorithm SHA256", dependencies)
        self.assertIn("#define\\s+BOOST_VERSION\\s+109200", dependencies)
        self.assertIn("#define\\s+BOOST_LIB_VERSION\\s+\"1_92\"", dependencies)
        self.assertIn("lib64-msvc-14.3", dependencies)
        self.assertIn("$mysqlVersion = '8.4.11'", dependencies)
        self.assertIn("https://cdn.mysql.com/archives/mysql-8.4/mysql-$mysqlVersion-winx64.zip", dependencies)
        self.assertIn(".mysql-version", dependencies)
        self.assertIn("lib\\libmysql.lib", dependencies)
        self.assertIn("lib\\libmysql.dll", dependencies)

        for retired in ("1.87.0", "boost_1_87_0", "mysql-8.4.9", "mysql-8.4.10", "8.0.46"):
            self.assertNotIn(retired, self.text)

    def test_core_configuration_is_relwithdebinfo_with_explicit_mysql_paths(self) -> None:
        configure = step(self.workflow, "build", "Configure AzerothCore for Windows")["run"]
        self.assertIn("CTYPE=\"RelWithDebInfo\"", configure)
        self.assertIn("-DBOOST_ROOT=C:/local/boost_1_92_0", configure)
        for option in (
            "-DMYSQL_ROOT_DIR=C:/tools/mysql/current",
            "-DMYSQL_INCLUDE_DIR=C:/tools/mysql/current/include",
            "-DMYSQL_LIBRARY=C:/tools/mysql/current/lib/libmysql.lib",
            "-DMYSQL_EXECUTABLE=C:/tools/mysql/current/bin/mysql.exe",
        ):
            self.assertIn(option, configure)
        self.assertIn("WriteAllText", configure)
        # The only remaining mention of the old build type is the explicit guard.
        self.assertIn("$written.Contains('CTYPE=\"Release\"')", configure)

    def test_installed_binaries_and_cmake_selection_are_verified(self) -> None:
        build_step = step(self.workflow, "build", "Build and install server")["run"]
        self.assertIn("authserver.exe", build_step)
        self.assertIn("worldserver.exe", build_step)
        self.assertIn("env/dist/$binary", build_step)

        verify = step(self.workflow, "build", "Verify CMake dependency selection")["run"]
        self.assertIn("RelWithDebInfo", verify)
        self.assertIn("MYSQL_LIBRARY", verify)
        self.assertIn("MYSQL_INCLUDE_DIR", verify)
        self.assertIn("MYSQL_EXECUTABLE", verify)
        self.assertIn("mysqlclient", verify)
        self.assertIn("boost_1_87", verify)
        self.assertIn("boost_1_92_0", verify)

    def test_msvc_toolset_and_boost_autolink_match_the_msvc_143_libraries(self) -> None:
        select = step(self.workflow, "build", "Select the MSVC 14.3-generation toolset")["run"]
        self.assertIn("VC\\Tools\\MSVC", select)
        self.assertIn("'^14\\.3\\.'", select)
        self.assertIn("'^14\\.4\\.'", select)
        self.assertIn("toolset=$selected", select)

        msvc = step(self.workflow, "build", "Set up MSVC")["with"]
        self.assertEqual(msvc["arch"], "x64")
        self.assertEqual(msvc["toolset"], "${{ steps.msvc-toolset.outputs.toolset }}")

        build = step(self.workflow, "build", "Build and install server")
        # The `/D` spelling is rewritten by MSYS before cl sees it, so the `-D`
        # form is mandatory for the bash build step.
        self.assertEqual(build["env"]["CL"], "-DBOOST_ALL_NO_LIB")
        self.assertNotIn("/DBOOST_ALL_NO_LIB", str(build["env"]))

        probe = step(self.workflow, "build", "Verify Boost linking with the selected toolset")["run"]
        self.assertIn("$env:CL = '-DBOOST_ALL_NO_LIB'", probe)
        self.assertIn("libboost_program_options-vc143-mt-x64-1_92.lib", probe)
        self.assertIn("lib64-msvc-14.3", probe)
        # Diagnostics must reach the check run even when job logs are unreachable.
        self.assertIn("::error title=Boost probe link failure::", probe)
        self.assertIn("::notice title=MSVC compiler::", probe)
        select = step(self.workflow, "build", "Select the MSVC 14.3-generation toolset")["run"]
        self.assertIn("::notice title=MSVC toolsets installed::", select)

        verify = step(self.workflow, "build", "Verify CMake dependency selection")["run"]
        self.assertIn("-vc143-", verify)
        # Boost resolves through its CMake config package, so the selected
        # libraries are verified on the generated link lines.
        self.assertIn("libboost_[A-Za-z0-9_\\-]+\\.lib", verify)
        self.assertIn("[regex]::Matches", verify)
        self.assertIn('::error title=$Title::$Message', verify)
        # Internal cache bookkeeping must not be mistaken for a MySQL path.
        self.assertIn("^(MYSQL_ROOT_DIR|MYSQL_INCLUDE_DIR|MYSQL_LIBRARY|MYSQL_EXECUTABLE|MYSQL_CONFIG):", verify)
        self.assertNotIn("$_ -match '[^']*mysql[^']*' } | Where-Object", verify)

    def test_a_clean_build_directory_is_required_before_configuration(self) -> None:
        names = [step_name for step_name in (s.get("name") for s in self.workflow["jobs"]["build"]["steps"]) if step_name]
        self.assertIn("Require a clean build directory", names)
        self.assertLess(
            names.index("Require a clean build directory"),
            names.index("Configure AzerothCore for Windows"),
        )
        guard = step(self.workflow, "build", "Require a clean build directory")["run"]
        self.assertIn("core\\var\\build\\obj", guard)
        self.assertIn("Remove-Item -Recurse -Force $buildDir", guard)
        self.assertIn("refusing to reuse a stale CMake cache", guard)

    def test_four_dll_staging_replaces_broad_dll_copying(self) -> None:
        staging = step(self.workflow, "build", "Stage Windows runtime DLL dependencies")["run"]
        self.assertIn("::error title=Runtime DLL staging::", staging)
        self.assertIn("core/env/runtime-dlls.json", staging)
        self.assertIn("::notice title=Runtime DLLs staged::", staging)
        self.assertIn("scripts/stage_windows_runtime_dlls.py", staging)
        self.assertIn("--mysql-root", staging)
        self.assertIn("--openssl-bin-dir", staging)
        self.assertIn("--output-dir", staging)
        self.assertIn("core/env/runtime-dlls", staging)
        # No broad "copy every DLL" loop from the OpenSSL/Boost/MySQL directories.
        self.assertNotIn("Get-ChildItem -LiteralPath $directory -Filter '*.dll'", self.text)
        self.assertNotIn("boost_1_92_0' + '\\\\lib64-msvc-14.3", self.text)

    def test_package_uses_the_root_layout_and_uploads_unpacked_contents(self) -> None:
        package = step(self.workflow, "build", "Package Windows runtime")["run"]
        self.assertIn("::error title=Runtime packaging::", package)
        for argument in ("--dist-dir", "--config-dir", "--dll-dir", "--mysql-root", "--output"):
            self.assertIn(argument, package)
        self.assertNotIn("--etc-dir", package)

        upload = step(self.workflow, "build", "Upload successful Windows runtime artifact")["with"]
        self.assertEqual(upload["path"], "runtime-package/azerothcore-ownedcore-windows/**")
        self.assertNotIn("runtime-package/azerothcore-ownedcore-windows.zip", self.text)

    def test_release_job_builds_exactly_one_zip_before_publishing(self) -> None:
        assemble = step(self.workflow, "release", "Assemble the single release ZIP")["run"]
        self.assertIn("scripts/assemble_release_zip.py", assemble)
        self.assertIn("--package-root release-assets/package-root", assemble)
        self.assertIn("--output release-assets/azerothcore-ownedcore-windows.zip", assemble)

        download = step(self.workflow, "release", "Download successful Windows runtime artifact")["with"]
        self.assertEqual(download["path"], "release-assets/package-root")

        publish = step(self.workflow, "release", "Publish GitHub Release")["with"]
        self.assertEqual(publish["files"], "release-assets/azerothcore-ownedcore-windows.zip")

    def test_integration_branch_pull_requests_trigger_both_workflows(self) -> None:
        self.assertEqual(
            self.workflow[True]["pull_request"]["branches"], ["main", "rebuild-897a41c"]
        )
        validate = yaml.safe_load((ROOT / ".github" / "workflows" / "validate.yml").read_text(encoding="utf-8"))
        self.assertEqual(
            validate[True]["pull_request"]["branches"], ["main", "rebuild-897a41c"]
        )

    def test_artifact_layout_is_verified_after_upload(self) -> None:
        verify = step(self.workflow, "verify-artifact", "Verify the artifact root layout")["run"]
        self.assertIn("scripts/verify_package_layout.py", verify)
        self.assertIn("--package-root artifact-root", verify)
        download = step(self.workflow, "verify-artifact", "Download the uploaded Windows runtime artifact")["with"]
        self.assertEqual(download["path"], "artifact-root")


if __name__ == "__main__":
    unittest.main()
