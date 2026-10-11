"""GitHub profile analysis service using official GitHub REST API with safe rate-limiting and caching."""
import re
import os
import requests
from flask import current_app

class GithubService:

    @staticmethod
    def extract_username(url):
        """Extract username from GitHub URL."""
        if not url:
            return None
        match = re.search(r"github\.com/([A-Za-z0-9_-]+)/?$", url.strip())
        return match.group(1) if match else None

    @classmethod
    def fetch_public_evidence(cls, github_url):
        """
        Fetches public repositories, descriptions, primary languages, and stars.
        Returns a structured evidence summary.
        """
        username = cls.extract_username(github_url)
        if not username:
            return {
                "status": "invalid_url",
                "summary": "Could not extract GitHub username from provided URL.",
                "repositories": [],
                "languages": [],
                "extracted_skills": []
            }

        headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "Adaptive-Interview-Intelligence/1.0"
        }
        token = os.environ.get("GITHUB_TOKEN") or current_app.config.get("GITHUB_TOKEN")
        if token:
            headers["Authorization"] = f"token {token}"

        api_url = f"https://api.github.com/users/{username}/repos?sort=updated&per_page=15"
        try:
            resp = requests.get(api_url, headers=headers, timeout=5)
            if resp.status_code == 200:
                repos = resp.json()
                parsed_repos = []
                languages = set()

                for r in repos:
                    if r.get("fork"):
                        continue  # Prioritize original candidate projects
                    lang = r.get("language")
                    if lang:
                        languages.add(lang)
                    parsed_repos.append({
                        "name": r.get("name"),
                        "description": r.get("description") or "No description provided",
                        "language": lang or "Not specified",
                        "stars": r.get("stargazers_count", 0),
                        "forks": r.get("forks_count", 0),
                        "url": r.get("html_url"),
                    })

                skills = list(languages)
                # Infer technologies from repo names or descriptions
                for r in parsed_repos:
                    text = f"{r['name']} {r['description']}".lower()
                    for tech in ["docker", "fastapi", "flask", "django", "react", "redis", "mongodb", "postgresql", "kafka", "aws", "kubernetes", "graphql"]:
                        if tech in text and tech.capitalize() not in skills:
                            skills.append(tech.capitalize())

                summary = f"GitHub user @{username} has {len(parsed_repos)} public source repositories primarily in {', '.join(list(languages)[:4]) or 'multiple stacks'}."

                return {
                    "status": "success",
                    "username": username,
                    "summary": summary,
                    "repositories": parsed_repos[:8],
                    "languages": list(languages),
                    "extracted_skills": skills,
                }
            elif resp.status_code == 404:
                return {
                    "status": "not_found",
                    "summary": f"GitHub user @{username} not found.",
                    "repositories": [],
                    "languages": [],
                    "extracted_skills": []
                }
            elif resp.status_code == 403:
                # Rate limited or forbidden
                return {
                    "status": "rate_limited",
                    "summary": f"GitHub API rate limit reached for unauthenticated requests. Retained profile URL for human recruiter verification.",
                    "repositories": [],
                    "languages": [],
                    "extracted_skills": []
                }
            else:
                return {
                    "status": "api_error",
                    "summary": f"GitHub API returned HTTP {resp.status_code}.",
                    "repositories": [],
                    "languages": [],
                    "extracted_skills": []
                }
        except requests.RequestException as e:
            return {
                "status": "network_error",
                "summary": f"Could not connect to GitHub API: {str(e)}. Profile URL recorded.",
                "repositories": [],
                "languages": [],
                "extracted_skills": []
            }
