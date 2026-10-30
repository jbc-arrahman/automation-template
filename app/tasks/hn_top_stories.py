"""Example 1 - read data from a page and return it as structured JSON.

    make run TASK=hn_top_stories INPUT="count=5"
    uv run bub run hn_top_stories --input count=5 --mode fresh --headless

Shows: start_url, allowed_domains, an Output model with a list, an optional input with a default.
"""
from typing import List

from pydantic import BaseModel, Field

from app.tasks.base import BaseTask


class Story(BaseModel):
    rank: int
    title: str
    points: int = Field(default=0, description="0 if the story shows no points")
    url: str = ""


class TopStories(BaseModel):
    stories: List[Story]


class HackerNewsTopStories(BaseTask):
    name = "hn_top_stories"
    description = "Read the top N stories from Hacker News (read-only example)."
    optional_inputs = {"count": 5}
    start_url = "https://news.ycombinator.com/"
    allowed_domains = ["news.ycombinator.com"]
    Output = TopStories
    max_steps = 8

    def prompt(self) -> str:
        n = int(self.inputs["count"])
        return f"""Collect the top {n} stories from the Hacker News front page.

Steps:
1. You are on https://news.ycombinator.com/. If not, open it.
2. Read the first {n} stories in rank order: rank number, title, points and the link URL.
   Read them from the page you see - do not open the stories.
3. Finish with done and the structured result.
"""

    def postprocess(self, output: TopStories) -> TopStories:
        output.stories = sorted(output.stories, key=lambda s: s.rank)[: int(self.inputs["count"])]
        return output
