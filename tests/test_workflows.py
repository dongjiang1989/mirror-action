"""
Tests for GitHub Actions workflow files added/modified in this PR:
  - .github/workflows/repos-mirror-gitea.yaml  (new)
  - .github/workflows/repos-mirror-gitlab.yaml (new)
  - .github/workflows/repos-mirror.yml         (renamed from repos-mirror-github.yml)
"""

import os
import unittest
import yaml

WORKFLOWS_DIR = os.path.join(os.path.dirname(__file__), "..", ".github", "workflows")

GITEA_WORKFLOW = os.path.join(WORKFLOWS_DIR, "repos-mirror-gitea.yaml")
GITLAB_WORKFLOW = os.path.join(WORKFLOWS_DIR, "repos-mirror-gitlab.yaml")
GITHUB_WORKFLOW = os.path.join(WORKFLOWS_DIR, "repos-mirror.yml")


def load_workflow(path):
    with open(path, "r") as f:
        return yaml.safe_load(f)


def get_triggers(workflow):
    """Return the 'on' trigger dict.

    PyYAML 1.1 parses the bare word ``on`` as the boolean ``True``, so the key
    may be stored as either the string ``"on"`` or the boolean ``True``
    depending on the PyYAML version / schema.  This helper handles both.
    """
    return workflow.get("on") or workflow.get(True)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_build_job(workflow):
    return workflow["jobs"]["build"]


def get_checkout_step(workflow):
    steps = get_build_job(workflow)["steps"]
    for step in steps:
        if step.get("uses", "").startswith("actions/checkout"):
            return step
    return None


def get_mirror_step(workflow):
    steps = get_build_job(workflow)["steps"]
    for step in steps:
        if "repos-mirror-action" in step.get("uses", ""):
            return step
    return None


# ===========================================================================
# repos-mirror-gitea.yaml
# ===========================================================================

class TestGiteaWorkflowFileExists(unittest.TestCase):
    def test_file_exists(self):
        self.assertTrue(
            os.path.isfile(GITEA_WORKFLOW),
            f"Expected workflow file to exist: {GITEA_WORKFLOW}",
        )


class TestGiteaWorkflowYAMLSyntax(unittest.TestCase):
    def test_valid_yaml(self):
        """File must be parseable YAML without errors."""
        doc = load_workflow(GITEA_WORKFLOW)
        self.assertIsInstance(doc, dict)

    def test_not_empty(self):
        doc = load_workflow(GITEA_WORKFLOW)
        self.assertTrue(doc)


class TestGiteaWorkflowTopLevelKeys(unittest.TestCase):
    def setUp(self):
        self.wf = load_workflow(GITEA_WORKFLOW)

    def test_has_name(self):
        self.assertIn("name", self.wf)

    def test_name_value(self):
        self.assertEqual(self.wf["name"], "Repos mirror sync gitea")

    def test_has_on_trigger(self):
        self.assertIsNotNone(get_triggers(self.wf), "'on' trigger block is missing")

    def test_has_jobs(self):
        self.assertIn("jobs", self.wf)


class TestGiteaWorkflowTriggers(unittest.TestCase):
    def setUp(self):
        self.on = get_triggers(load_workflow(GITEA_WORKFLOW))

    def test_has_push_trigger(self):
        self.assertIn("push", self.on)

    def test_has_pull_request_trigger(self):
        self.assertIn("pull_request", self.on)

    def test_push_includes_master_branch(self):
        branches = self.on["push"]["branches"]
        self.assertIn("master", branches)

    def test_push_includes_version_branches(self):
        """Gitea workflow should trigger on version branches (v.*) unlike the base workflow."""
        branches = self.on["push"]["branches"]
        self.assertIn("v.*", branches)

    def test_pull_request_targets_master(self):
        branches = self.on["pull_request"]["branches"]
        self.assertIn("master", branches)

    def test_pull_request_does_not_trigger_on_version_branches(self):
        """PRs should only target master, not version branches."""
        branches = self.on["pull_request"]["branches"]
        self.assertNotIn("v.*", branches)


class TestGiteaWorkflowJob(unittest.TestCase):
    def setUp(self):
        self.wf = load_workflow(GITEA_WORKFLOW)
        self.job = get_build_job(self.wf)

    def test_build_job_exists(self):
        self.assertIn("build", self.wf["jobs"])

    def test_runs_on_ubuntu_latest(self):
        self.assertEqual(self.job["runs-on"], "ubuntu-latest")

    def test_has_steps(self):
        self.assertIn("steps", self.job)
        self.assertIsInstance(self.job["steps"], list)
        self.assertGreater(len(self.job["steps"]), 0)


class TestGiteaWorkflowCheckoutStep(unittest.TestCase):
    def setUp(self):
        self.wf = load_workflow(GITEA_WORKFLOW)
        self.step = get_checkout_step(self.wf)

    def test_checkout_step_exists(self):
        self.assertIsNotNone(self.step, "actions/checkout step not found")

    def test_checkout_action_version(self):
        self.assertEqual(self.step["uses"], "actions/checkout@v2")

    def test_fetch_depth_zero(self):
        """fetch-depth: 0 ensures full history is available for mirroring."""
        self.assertEqual(self.step["with"]["fetch-depth"], 0)

    def test_persist_credentials_false(self):
        """persist-credentials: false prevents leaking credentials into subprocesses."""
        self.assertFalse(self.step["with"]["persist-credentials"])


class TestGiteaWorkflowMirrorStep(unittest.TestCase):
    def setUp(self):
        self.wf = load_workflow(GITEA_WORKFLOW)
        self.step = get_mirror_step(self.wf)

    def test_mirror_step_exists(self):
        self.assertIsNotNone(self.step, "repos-mirror-action step not found")

    def test_uses_pinned_action_version(self):
        self.assertEqual(
            self.step["uses"],
            "kubeservice-stack/repos-mirror-action@v1.0.3",
        )

    def test_target_url_points_to_gitea(self):
        url = self.step["with"]["target-url"]
        self.assertIn("gitea.com", url)

    def test_target_url_full_value(self):
        self.assertEqual(
            self.step["with"]["target-url"],
            "https://gitea.com/dongjiang1989/repos-mirror.git",
        )

    def test_target_username(self):
        self.assertEqual(self.step["with"]["target-username"], "dongjiang1989")

    def test_target_token_uses_secret(self):
        """Token must reference a GitHub secret, not be a plaintext value."""
        token = self.step["with"]["target-token"]
        self.assertIn("secrets.GITEA_ACTOR_SECRET", token)

    def test_target_token_not_hardcoded(self):
        """Token must not be a bare string credential."""
        token = self.step["with"]["target-token"]
        self.assertTrue(
            token.strip().startswith("${{"),
            "Token should use GitHub secrets expression syntax",
        )

    def test_target_url_uses_https(self):
        url = self.step["with"]["target-url"]
        self.assertTrue(url.startswith("https://"), "Target URL should use HTTPS")

    def test_target_url_ends_with_git(self):
        url = self.step["with"]["target-url"]
        self.assertTrue(url.endswith(".git"), "Target URL should end with .git")


# ===========================================================================
# repos-mirror-gitlab.yaml
# ===========================================================================

class TestGitlabWorkflowFileExists(unittest.TestCase):
    def test_file_exists(self):
        self.assertTrue(
            os.path.isfile(GITLAB_WORKFLOW),
            f"Expected workflow file to exist: {GITLAB_WORKFLOW}",
        )


class TestGitlabWorkflowYAMLSyntax(unittest.TestCase):
    def test_valid_yaml(self):
        doc = load_workflow(GITLAB_WORKFLOW)
        self.assertIsInstance(doc, dict)

    def test_not_empty(self):
        doc = load_workflow(GITLAB_WORKFLOW)
        self.assertTrue(doc)


class TestGitlabWorkflowTopLevelKeys(unittest.TestCase):
    def setUp(self):
        self.wf = load_workflow(GITLAB_WORKFLOW)

    def test_has_name(self):
        self.assertIn("name", self.wf)

    def test_name_value(self):
        self.assertEqual(self.wf["name"], "Repos mirror sync gitlab")

    def test_has_on_trigger(self):
        self.assertIsNotNone(get_triggers(self.wf), "'on' trigger block is missing")

    def test_has_jobs(self):
        self.assertIn("jobs", self.wf)


class TestGitlabWorkflowTriggers(unittest.TestCase):
    def setUp(self):
        self.on = get_triggers(load_workflow(GITLAB_WORKFLOW))

    def test_has_push_trigger(self):
        self.assertIn("push", self.on)

    def test_has_pull_request_trigger(self):
        self.assertIn("pull_request", self.on)

    def test_push_includes_master_branch(self):
        branches = self.on["push"]["branches"]
        self.assertIn("master", branches)

    def test_push_includes_version_branches(self):
        """GitLab workflow should trigger on version branches (v.*)."""
        branches = self.on["push"]["branches"]
        self.assertIn("v.*", branches)

    def test_pull_request_targets_master(self):
        branches = self.on["pull_request"]["branches"]
        self.assertIn("master", branches)

    def test_pull_request_does_not_trigger_on_version_branches(self):
        branches = self.on["pull_request"]["branches"]
        self.assertNotIn("v.*", branches)


class TestGitlabWorkflowJob(unittest.TestCase):
    def setUp(self):
        self.wf = load_workflow(GITLAB_WORKFLOW)
        self.job = get_build_job(self.wf)

    def test_build_job_exists(self):
        self.assertIn("build", self.wf["jobs"])

    def test_runs_on_ubuntu_latest(self):
        self.assertEqual(self.job["runs-on"], "ubuntu-latest")

    def test_has_steps(self):
        self.assertIn("steps", self.job)
        self.assertIsInstance(self.job["steps"], list)
        self.assertGreater(len(self.job["steps"]), 0)


class TestGitlabWorkflowCheckoutStep(unittest.TestCase):
    def setUp(self):
        self.wf = load_workflow(GITLAB_WORKFLOW)
        self.step = get_checkout_step(self.wf)

    def test_checkout_step_exists(self):
        self.assertIsNotNone(self.step, "actions/checkout step not found")

    def test_checkout_action_version(self):
        self.assertEqual(self.step["uses"], "actions/checkout@v2")

    def test_fetch_depth_zero(self):
        self.assertEqual(self.step["with"]["fetch-depth"], 0)

    def test_persist_credentials_false(self):
        self.assertFalse(self.step["with"]["persist-credentials"])


class TestGitlabWorkflowMirrorStep(unittest.TestCase):
    def setUp(self):
        self.wf = load_workflow(GITLAB_WORKFLOW)
        self.step = get_mirror_step(self.wf)

    def test_mirror_step_exists(self):
        self.assertIsNotNone(self.step, "repos-mirror-action step not found")

    def test_uses_pinned_action_version(self):
        self.assertEqual(
            self.step["uses"],
            "kubeservice-stack/repos-mirror-action@v1.0.3",
        )

    def test_target_url_points_to_gitlab(self):
        url = self.step["with"]["target-url"]
        self.assertIn("gitlab.com", url)

    def test_target_url_full_value(self):
        self.assertEqual(
            self.step["with"]["target-url"],
            "https://gitlab.com/kubeservice-stack/repos-mirror.git",
        )

    def test_target_username(self):
        self.assertEqual(self.step["with"]["target-username"], "dongjiang")

    def test_target_token_uses_secret(self):
        token = self.step["with"]["target-token"]
        self.assertIn("secrets.GITLAB_ACTOR_SECRET", token)

    def test_target_token_not_hardcoded(self):
        token = self.step["with"]["target-token"]
        self.assertTrue(
            token.strip().startswith("${{"),
            "Token should use GitHub secrets expression syntax",
        )

    def test_target_url_uses_https(self):
        url = self.step["with"]["target-url"]
        self.assertTrue(url.startswith("https://"))

    def test_target_url_ends_with_git(self):
        url = self.step["with"]["target-url"]
        self.assertTrue(url.endswith(".git"))

    def test_gitlab_url_does_not_reference_gitea(self):
        """GitLab workflow must not accidentally point to a Gitea URL."""
        url = self.step["with"]["target-url"]
        self.assertNotIn("gitea.com", url)

    def test_gitlab_secret_differs_from_gitea_secret(self):
        """Each provider must use its own distinct secret."""
        gitea_wf = load_workflow(GITEA_WORKFLOW)
        gitea_token = get_mirror_step(gitea_wf)["with"]["target-token"]
        gitlab_token = self.step["with"]["target-token"]
        self.assertNotEqual(
            gitea_token,
            gitlab_token,
            "Gitea and GitLab workflows must reference different secrets",
        )


# ===========================================================================
# repos-mirror.yml  (renamed from repos-mirror-github.yml — content unchanged)
# ===========================================================================

class TestGithubWorkflowFileExists(unittest.TestCase):
    def test_file_exists_at_new_path(self):
        """File should exist at the new path repos-mirror.yml."""
        self.assertTrue(
            os.path.isfile(GITHUB_WORKFLOW),
            f"Expected workflow file at renamed path: {GITHUB_WORKFLOW}",
        )

    def test_old_filename_does_not_exist(self):
        """Old filename repos-mirror-github.yml should no longer exist."""
        old_path = os.path.join(WORKFLOWS_DIR, "repos-mirror-github.yml")
        self.assertFalse(
            os.path.isfile(old_path),
            "Old workflow filename repos-mirror-github.yml should have been removed",
        )


class TestGithubWorkflowYAMLSyntax(unittest.TestCase):
    def test_valid_yaml(self):
        doc = load_workflow(GITHUB_WORKFLOW)
        self.assertIsInstance(doc, dict)


class TestGithubWorkflowTopLevelKeys(unittest.TestCase):
    def setUp(self):
        self.wf = load_workflow(GITHUB_WORKFLOW)

    def test_has_name(self):
        self.assertIn("name", self.wf)

    def test_name_value(self):
        self.assertEqual(self.wf["name"], "Repos mirror sync")

    def test_has_on_trigger(self):
        self.assertIsNotNone(get_triggers(self.wf), "'on' trigger block is missing")

    def test_has_jobs(self):
        self.assertIn("jobs", self.wf)


class TestGithubWorkflowTriggers(unittest.TestCase):
    def setUp(self):
        self.on = get_triggers(load_workflow(GITHUB_WORKFLOW))

    def test_push_triggers_on_master_only(self):
        """Base GitHub workflow only pushes from master, unlike gitea/gitlab which also include v.*."""
        branches = self.on["push"]["branches"]
        self.assertEqual(branches, ["master"])

    def test_push_does_not_include_version_branches(self):
        branches = self.on["push"]["branches"]
        self.assertNotIn("v.*", branches)

    def test_pull_request_targets_master(self):
        branches = self.on["pull_request"]["branches"]
        self.assertIn("master", branches)


class TestGithubWorkflowMirrorStep(unittest.TestCase):
    def setUp(self):
        self.wf = load_workflow(GITHUB_WORKFLOW)
        self.step = get_mirror_step(self.wf)

    def test_mirror_step_exists(self):
        self.assertIsNotNone(self.step)

    def test_uses_pinned_action_version(self):
        self.assertEqual(
            self.step["uses"],
            "kubeservice-stack/repos-mirror-action@v1.0.3",
        )

    def test_target_url_points_to_github(self):
        url = self.step["with"]["target-url"]
        self.assertIn("github.com", url)

    def test_target_token_uses_secret(self):
        token = self.step["with"]["target-token"]
        self.assertIn("secrets.ACTOR_SECRET", token)

    def test_target_token_not_hardcoded(self):
        token = self.step["with"]["target-token"]
        self.assertTrue(token.strip().startswith("${{"))

    def test_github_secret_differs_from_gitea_secret(self):
        gitea_wf = load_workflow(GITEA_WORKFLOW)
        gitea_token = get_mirror_step(gitea_wf)["with"]["target-token"]
        github_token = self.step["with"]["target-token"]
        self.assertNotEqual(github_token, gitea_token)

    def test_github_secret_differs_from_gitlab_secret(self):
        gitlab_wf = load_workflow(GITLAB_WORKFLOW)
        gitlab_token = get_mirror_step(gitlab_wf)["with"]["target-token"]
        github_token = self.step["with"]["target-token"]
        self.assertNotEqual(github_token, gitlab_token)


# ===========================================================================
# Cross-workflow consistency checks
# ===========================================================================

class TestWorkflowConsistency(unittest.TestCase):
    def setUp(self):
        self.gitea_wf = load_workflow(GITEA_WORKFLOW)
        self.gitlab_wf = load_workflow(GITLAB_WORKFLOW)
        self.github_wf = load_workflow(GITHUB_WORKFLOW)

    def test_all_workflows_use_same_action_version(self):
        """All mirror workflows must pin to the same action version."""
        gitea_action = get_mirror_step(self.gitea_wf)["uses"]
        gitlab_action = get_mirror_step(self.gitlab_wf)["uses"]
        github_action = get_mirror_step(self.github_wf)["uses"]
        self.assertEqual(gitea_action, gitlab_action)
        self.assertEqual(gitlab_action, github_action)

    def test_all_workflows_use_same_checkout_version(self):
        gitea_co = get_checkout_step(self.gitea_wf)["uses"]
        gitlab_co = get_checkout_step(self.gitlab_wf)["uses"]
        github_co = get_checkout_step(self.github_wf)["uses"]
        self.assertEqual(gitea_co, gitlab_co)
        self.assertEqual(gitlab_co, github_co)

    def test_all_workflows_run_on_ubuntu_latest(self):
        for wf, label in [
            (self.gitea_wf, "gitea"),
            (self.gitlab_wf, "gitlab"),
            (self.github_wf, "github"),
        ]:
            with self.subTest(workflow=label):
                self.assertEqual(get_build_job(wf)["runs-on"], "ubuntu-latest")

    def test_all_target_urls_are_unique(self):
        gitea_url = get_mirror_step(self.gitea_wf)["with"]["target-url"]
        gitlab_url = get_mirror_step(self.gitlab_wf)["with"]["target-url"]
        github_url = get_mirror_step(self.github_wf)["with"]["target-url"]
        urls = {gitea_url, gitlab_url, github_url}
        self.assertEqual(
            len(urls),
            3,
            "Each workflow must mirror to a distinct target URL",
        )

    def test_all_secrets_are_unique(self):
        """Each workflow must use its own provider-specific secret."""
        gitea_tok = get_mirror_step(self.gitea_wf)["with"]["target-token"]
        gitlab_tok = get_mirror_step(self.gitlab_wf)["with"]["target-token"]
        github_tok = get_mirror_step(self.github_wf)["with"]["target-token"]
        secrets = {gitea_tok, gitlab_tok, github_tok}
        self.assertEqual(
            len(secrets),
            3,
            "Each workflow must reference a distinct secret token",
        )

    def test_new_workflows_have_version_branch_trigger(self):
        """New gitea and gitlab workflows add v.* branch triggering which the base workflow lacks."""
        gitea_branches = get_triggers(self.gitea_wf)["push"]["branches"]
        gitlab_branches = get_triggers(self.gitlab_wf)["push"]["branches"]
        github_branches = get_triggers(self.github_wf)["push"]["branches"]
        self.assertIn("v.*", gitea_branches)
        self.assertIn("v.*", gitlab_branches)
        self.assertNotIn("v.*", github_branches)

    def test_all_workflows_have_fetch_depth_zero(self):
        for wf, label in [
            (self.gitea_wf, "gitea"),
            (self.gitlab_wf, "gitlab"),
            (self.github_wf, "github"),
        ]:
            with self.subTest(workflow=label):
                co_step = get_checkout_step(wf)
                self.assertEqual(co_step["with"]["fetch-depth"], 0)

    def test_all_workflows_disable_persist_credentials(self):
        for wf, label in [
            (self.gitea_wf, "gitea"),
            (self.gitlab_wf, "gitlab"),
            (self.github_wf, "github"),
        ]:
            with self.subTest(workflow=label):
                co_step = get_checkout_step(wf)
                self.assertFalse(co_step["with"]["persist-credentials"])

    def test_workflow_names_are_unique(self):
        names = {
            self.gitea_wf["name"],
            self.gitlab_wf["name"],
            self.github_wf["name"],
        }
        self.assertEqual(len(names), 3, "Each workflow must have a unique name")

    # Regression: ensure no workflow accidentally omits the mirror step entirely
    def test_no_workflow_missing_mirror_step(self):
        for wf, label in [
            (self.gitea_wf, "gitea"),
            (self.gitlab_wf, "gitlab"),
            (self.github_wf, "github"),
        ]:
            with self.subTest(workflow=label):
                self.assertIsNotNone(
                    get_mirror_step(wf),
                    f"{label} workflow is missing the repos-mirror-action step",
                )


if __name__ == "__main__":
    unittest.main(verbosity=2)
