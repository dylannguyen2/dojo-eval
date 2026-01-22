#!/usr/bin/env python3
"""
Scanner for Weibo data to check task requirements.
Analyzes parsed_data.json and reports what data is available vs missing for each task.
"""

import argparse
import json
import re
from pathlib import Path
from collections import defaultdict
from typing import List, Dict, Set, Tuple


class TaskScanner:
    """Scanner to check if data meets task requirements."""

    def __init__(self, data: dict):
        self.data = data
        self.users = data.get("users", [])
        self.posts = data.get("posts", [])
        self.comments = data.get("comments", [])
        self.replies = data.get("replies", [])
        self.trending_topics = data.get("trendingTopics", [])
        self.hashtag_topics = data.get("hashtagTopics", [])
        self.custom_groups = data.get("customGroups", [])

        # Build indexes for fast lookup
        self._build_indexes()

    def _build_indexes(self):
        """Build indexes for efficient querying."""
        # Map user_id to user
        self.user_by_id = {u["_id"]: u for u in self.users}

        # Map user_id to their posts
        self.posts_by_user = defaultdict(list)
        for post in self.posts:
            if "user" in post and "_id" in post["user"]:
                self.posts_by_user[post["user"]["_id"]].append(post)

        # Map post_id to post
        self.post_by_id = {p["_id"]: p for p in self.posts}

        # Map post_id to comments
        self.comments_by_post = defaultdict(list)
        for comment in self.comments:
            if "postId" in comment:
                self.comments_by_post[comment["postId"]].append(comment)

    def print_task_header(self, task_num: int, description: str):
        """Print a consistent task header."""
        print(f"\n┌─ TASK {task_num} " + "─" * (60 - len(str(task_num))))
        print(f"│ {description}")
        print("└" + "─" * 69)

    def print_example_post(self, post: dict):
        """Print an example post in markdown format."""
        if post:
            print(f"\n    📝 Example Post:")
            print(f"       Author:  {post.get('user', {}).get('name', 'Unknown')}")
            print(f"       Content: {post.get('content', 'N/A')[:100]}...")
            print(f"       Link:    https://weibo.com/{post.get('_id', '')}")

    def contains_any_keyword(self, text: str, keywords: List[str]) -> bool:
        """Check if text contains any of the keywords."""
        if not text:
            return False
        text_lower = text.lower()
        return any(keyword.lower() in text_lower for keyword in keywords)

    def contains_all_keywords(self, text: str, keywords: List[str]) -> bool:
        """Check if text contains all of the keywords."""
        if not text:
            return False
        text_lower = text.lower()
        return all(keyword.lower() in text_lower for keyword in keywords)

    def post_matches_keywords(self, post: dict, keywords: List[str]) -> bool:
        """Check if post content or hashtags contain keywords."""
        # Check content
        if self.contains_any_keyword(post.get("content", ""), keywords):
            return True

        # Check hashtags
        hashtags = post.get("hashtags", [])
        for hashtag in hashtags:
            hashtag_text = hashtag.get("text", "").strip("#")
            if self.contains_any_keyword(hashtag_text, keywords):
                return True

        return False

    def get_users_with_posts_containing(self, keywords: List[str], min_posts: int = 1) -> List[Dict]:
        """Get users who have at least min_posts containing any of the keywords."""
        results = []

        for user_id, user_posts in self.posts_by_user.items():
            matching_posts = [p for p in user_posts if self.post_matches_keywords(p, keywords)]

            if len(matching_posts) >= min_posts:
                user = self.user_by_id.get(user_id)
                if user:
                    results.append({
                        "user": user,
                        "matching_posts": matching_posts,
                        "match_count": len(matching_posts)
                    })

        return results

    def is_uninteresting_post(self, post: dict) -> bool:
        """Check if post is uninteresting (repost or short without quality keywords)."""
        content = post.get("content", "")

        # Check if it's a repost
        if "转发" in content:
            return True

        # Check if content is too short without quality keywords
        if len(content) < 10:
            quality_keywords = ["推荐", "分享", "讨论", "观点", "想法", "体验", "感受"]
            if not self.contains_any_keyword(content, quality_keywords):
                return True

        return False

    def get_trending_topics_with_keywords(self, keywords: List[str]) -> List[Dict]:
        """Get trending topics containing keywords."""
        results = []

        for topic in self.trending_topics:
            topic_text = topic.get("text", "")
            if self.contains_any_keyword(topic_text, keywords):
                results.append(topic)

        return results

    def get_posts_in_topic(self, topic_text: str, keywords: List[str]) -> List[Dict]:
        """Get posts related to a topic (matching keywords)."""
        matching_posts = []

        for post in self.posts:
            if self.post_matches_keywords(post, keywords):
                matching_posts.append(post)

        return matching_posts

    def get_custom_groups_with_name(self, keywords: List[str]) -> List[Dict]:
        """Get custom groups with names containing keywords."""
        results = []

        for group in self.custom_groups:
            group_name = group.get("name", "")
            if self.contains_any_keyword(group_name, keywords):
                results.append(group)

        return results

    def scan_all_tasks(self) -> Dict:
        """Scan all tasks and return results."""
        results = {}

        print("\n" + "=" * 70)
        print("📊 WEIBO DATA TASK SCANNER".center(70))
        print("=" * 70)

        print(f"\n📦 Data Overview:")
        print(f"   • Users:           {len(self.users):,}")
        print(f"   • Posts:           {len(self.posts):,}")
        print(f"   • Comments:        {len(self.comments):,}")
        print(f"   • Replies:         {len(self.replies):,}")
        print(f"   • Trending Topics: {len(self.trending_topics):,}")
        print(f"   • Hashtag Topics:  {len(self.hashtag_topics):,}")
        print(f"   • Custom Groups:   {len(self.custom_groups):,}")
        print("\n" + "=" * 70 + "\n")

        # Task 3
        results['task3'] = self.scan_task3()

        # Task 6
        results['task6'] = self.scan_task6()

        # Task 7
        results['task7'] = self.scan_task7()

        # Task 8
        results['task8'] = self.scan_task8()

        # Task 9
        results['task9'] = self.scan_task9()

        # Task 11
        results['task11'] = self.scan_task11()

        # Task 12
        results['task12'] = self.scan_task12()

        # Task 15
        results['task15'] = self.scan_task15()

        # Task 16
        results['task16'] = self.scan_task16()

        # Task 17
        results['task17'] = self.scan_task17()

        # Task 18
        results['task18'] = self.scan_task18()

        # Task 19
        results['task19'] = self.scan_task19()

        # Task 21
        results['task21'] = self.scan_task21()

        # Task 23
        results['task23'] = self.scan_task23()

        # Task 24
        results['task24'] = self.scan_task24()

        # Task 26
        results['task26'] = self.scan_task26()

        # Task 27
        results['task27'] = self.scan_task27()

        # Task 28
        results['task28'] = self.scan_task28()

        # Task 29
        results['task29'] = self.scan_task29()

        # Task 30
        results['task30'] = self.scan_task30()

        # Task 31
        results['task31'] = self.scan_task31()

        # Task 32
        results['task32'] = self.scan_task32()

        # Task 33
        results['task33'] = self.scan_task33()

        # Task 34
        results['task34'] = self.scan_task34()

        # Task 35
        results['task35'] = self.scan_task35()

        # Task 37
        results['task37'] = self.scan_task37()

        # Task 39
        results['task39'] = self.scan_task39()

        # Task 40
        results['task40'] = self.scan_task40()

        # Task 41
        results['task41'] = self.scan_task41()

        # Task 42
        results['task42'] = self.scan_task42()

        # Task 43
        results['task43'] = self.scan_task43()

        # Task 44
        results['task44'] = self.scan_task44()

        # Task 45
        results['task45'] = self.scan_task45()

        # Task 47
        results['task47'] = self.scan_task47()

        # Task 48
        results['task48'] = self.scan_task48()

        return results

    def scan_task3(self) -> Dict:
        """Task 3: 1 user with max followers who posted about AI + 5 recent posts about AI or tech hashtags."""
        self.print_task_header(3, "AI User with Max Followers + 5 Recent AI/Tech Posts")

        keywords = ["人工智能"]
        tech_keywords = ["人工智能", "科技"]

        # Find users who posted about AI
        ai_users = self.get_users_with_posts_containing(keywords, min_posts=1)

        if not ai_users:
            print("  ❌ No users found who posted about '人工智能'\n")
            return {"status": "FAIL", "found": 0, "required": 1}

        # Sort by followers count
        ai_users_sorted = sorted(ai_users, key=lambda x: x["user"].get("followersCount", 0), reverse=True)
        top_user = ai_users_sorted[0]

        # Get their posts with AI or tech hashtags
        user_posts = self.posts_by_user.get(top_user["user"]["_id"], [])
        tech_posts = [p for p in user_posts if self.post_matches_keywords(p, tech_keywords)]

        # Sort by timestamp (most recent first)
        tech_posts_sorted = sorted(tech_posts, key=lambda x: x.get("timestamp", ""), reverse=True)
        recent_5 = tech_posts_sorted[:5]

        print(f"  👤 User:        {top_user['user']['name']} (ID: {top_user['user']['_id']})")
        print(f"  👥 Followers:   {top_user['user'].get('followersCount', 0):,}")
        print(f"  📝 AI posts:    {len(top_user['matching_posts'])}")
        print(f"  💻 Tech posts:  {len(tech_posts)}")
        print(f"  🔥 Recent 5:    {len(recent_5)}")

        # Print example post
        if recent_5:
            self.print_example_post(recent_5[0])

        if len(recent_5) >= 5:
            print("\n  ✅ PASS: Found user with 5+ recent tech posts\n")
            return {"status": "PASS", "user": top_user["user"], "posts": recent_5}
        else:
            print(f"\n  ⚠️  PARTIAL: User only has {len(recent_5)} tech posts (need 5)\n")
            return {"status": "PARTIAL", "user": top_user["user"], "posts": recent_5}

    def scan_task6(self) -> Dict:
        """Task 6: 3 users with posts about Shanghai/food/travel."""
        self.print_task_header(6, "3 Users with Shanghai/Food/Travel Posts")

        keywords = ["上海", "美食", "旅行", "餐厅", "景点", "小吃", "旅游", "推荐"]
        users = self.get_users_with_posts_containing(keywords, min_posts=1)

        print(f"  📊 Found {len(users)} users with matching posts\n")

        if len(users) >= 3:
            for i, user_data in enumerate(users[:3], 1):
                print(f"     {i}. {user_data['user']['name']} (ID: {user_data['user']['_id']}) - {user_data['match_count']} posts")

            # Print example post
            if users[0]["matching_posts"]:
                self.print_example_post(users[0]["matching_posts"][0])

            print("\n  ✅ PASS: Found 3+ users\n")
            return {"status": "PASS", "found": len(users), "required": 3, "users": users[:3]}
        else:
            print(f"\n  ❌ FAIL: Only found {len(users)} users (need 3)\n")
            return {"status": "FAIL", "found": len(users), "required": 3, "users": users}

    def scan_task7(self) -> Dict:
        """Task 7: 4 users who posted about reading."""
        self.print_task_header(7, "4 Users with Reading Posts")

        keywords = ["读书"]
        users = self.get_users_with_posts_containing(keywords, min_posts=1)

        print(f"  📊 Found {len(users)} users with matching posts\n")

        if len(users) >= 4:
            for i, user_data in enumerate(users[:4], 1):
                print(f"     {i}. {user_data['user']['name']} (ID: {user_data['user']['_id']}) - {user_data['match_count']} posts")

            # Print example post
            if users[0]["matching_posts"]:
                self.print_example_post(users[0]["matching_posts"][0])

            print("\n  ✅ PASS: Found 4+ users\n")
            return {"status": "PASS", "found": len(users), "required": 4, "users": users[:4]}
        else:
            print(f"\n  ❌ FAIL: Only found {len(users)} users (need 4)\n")
            return {"status": "FAIL", "found": len(users), "required": 4, "users": users}

    def scan_task8(self) -> Dict:
        """Task 8: 3 posts from different authors about fitness."""
        self.print_task_header(8, "3 Fitness Posts from Different Authors")

        keywords = ["健身", "运动", "锻炼", "训练", "跑步", "瑜伽"]

        # Find posts matching keywords
        matching_posts = [p for p in self.posts if self.post_matches_keywords(p, keywords)]

        # Group by author
        posts_by_author = defaultdict(list)
        for post in matching_posts:
            if "user" in post and "_id" in post["user"]:
                posts_by_author[post["user"]["_id"]].append(post)

        # Take one post per author
        unique_author_posts = []
        for _, posts in posts_by_author.items():
            unique_author_posts.append(posts[0])

        print(f"  📊 Found {len(matching_posts)} fitness posts from {len(unique_author_posts)} unique authors\n")

        if len(unique_author_posts) >= 3:
            for i, post in enumerate(unique_author_posts[:3], 1):
                user_name = post.get("user", {}).get("name", "Unknown")
                content_preview = post.get("content", "")[:50]
                print(f"     {i}. {user_name}: {content_preview}...")

            # Print example post
            self.print_example_post(unique_author_posts[0])

            print("\n  ✅ PASS: Found 3+ posts from different authors\n")
            return {"status": "PASS", "found": len(unique_author_posts), "required": 3, "posts": unique_author_posts[:3]}
        else:
            print(f"\n  ❌ FAIL: Only found {len(unique_author_posts)} posts (need 3)\n")
            return {"status": "FAIL", "found": len(unique_author_posts), "required": 3, "posts": unique_author_posts}

    def scan_task9(self) -> Dict:
        """Task 9: 2 users with 5 uninteresting posts each."""
        self.print_task_header(9, "2 Users with 5 Uninteresting Posts Each")

        users_with_uninteresting = []

        for user_id, user_posts in self.posts_by_user.items():
            uninteresting_posts = [p for p in user_posts if self.is_uninteresting_post(p)]

            if len(uninteresting_posts) >= 5:
                user = self.user_by_id.get(user_id)
                if user:
                    users_with_uninteresting.append({
                        "user": user,
                        "uninteresting_posts": uninteresting_posts,
                        "count": len(uninteresting_posts)
                    })

        print(f"  📊 Found {len(users_with_uninteresting)} users with 5+ uninteresting posts\n")

        if len(users_with_uninteresting) >= 2:
            for i, user_data in enumerate(users_with_uninteresting[:2], 1):
                print(f"     {i}. {user_data['user']['name']} (ID: {user_data['user']['_id']}) - {user_data['count']} uninteresting posts")

            # Print example post
            if users_with_uninteresting[0]["uninteresting_posts"]:
                self.print_example_post(users_with_uninteresting[0]["uninteresting_posts"][0])

            print("\n  ✅ PASS: Found 2+ users\n")
            return {"status": "PASS", "found": len(users_with_uninteresting), "required": 2, "users": users_with_uninteresting[:2]}
        else:
            print(f"\n  ❌ FAIL: Only found {len(users_with_uninteresting)} users (need 2)\n")
            return {"status": "FAIL", "found": len(users_with_uninteresting), "required": 2, "users": users_with_uninteresting}

    def scan_task11(self) -> Dict:
        """Task 11: 2 users with 5 posts each about basketball/NBA."""
        self.print_task_header(11, "2 Users with 5 Basketball/NBA Posts Each")

        keywords = ["篮球", "NBA", "比赛", "球员", "球队", "精彩", "集锦"]
        users = self.get_users_with_posts_containing(keywords, min_posts=5)

        print(f"  📊 Found {len(users)} users with 5+ matching posts\n")

        if len(users) >= 2:
            for i, user_data in enumerate(users[:2], 1):
                print(f"     {i}. {user_data['user']['name']} (ID: {user_data['user']['_id']}) - {user_data['match_count']} posts")

            # Print example post
            if users[0]["matching_posts"]:
                self.print_example_post(users[0]["matching_posts"][0])

            print("\n  ✅ PASS: Found 2+ users\n")
            return {"status": "PASS", "found": len(users), "required": 2, "users": users[:2]}
        else:
            print(f"\n  ❌ FAIL: Only found {len(users)} users (need 2)\n")
            return {"status": "FAIL", "found": len(users), "required": 2, "users": users}

    def scan_task12(self) -> Dict:
        """Task 12: 1 user with photography posts."""
        self.print_task_header(12, "1 User with Photography Posts")

        keywords = ["摄影", "照片", "拍照", "相机", "镜头", "摄影作品"]
        users = self.get_users_with_posts_containing(keywords, min_posts=1)

        print(f"  📊 Found {len(users)} users with matching posts\n")

        if len(users) >= 1:
            user_data = users[0]
            print(f"     1. {user_data['user']['name']} (ID: {user_data['user']['_id']}) - {user_data['match_count']} posts")

            # Print example post
            if user_data["matching_posts"]:
                self.print_example_post(user_data["matching_posts"][0])

            print("\n  ✅ PASS: Found 1+ users\n")
            return {"status": "PASS", "found": len(users), "required": 1, "users": users[:1]}
        else:
            print("\n  ❌ FAIL: No users found\n")
            return {"status": "FAIL", "found": 0, "required": 1, "users": []}

    def scan_task15(self) -> Dict:
        """Task 15: 2 users with tech/AI posts."""
        self.print_task_header(15, "2 Users with Tech/AI Posts")

        keywords = ["科技", "技术", "资讯", "新闻", "人工智能", "AI", "互联网", "创新"]
        users = self.get_users_with_posts_containing(keywords, min_posts=1)

        print(f"  📊 Found {len(users)} users with matching posts\n")

        if len(users) >= 2:
            for i, user_data in enumerate(users[:2], 1):
                print(f"     {i}. {user_data['user']['name']} (ID: {user_data['user']['_id']}) - {user_data['match_count']} posts")

            # Print example post
            if users[0]["matching_posts"]:
                self.print_example_post(users[0]["matching_posts"][0])

            print("\n  ✅ PASS: Found 2+ users\n")
            return {"status": "PASS", "found": len(users), "required": 2, "users": users[:2]}
        else:
            print(f"\n  ❌ FAIL: Only found {len(users)} users (need 2)\n")
            return {"status": "FAIL", "found": len(users), "required": 2, "users": users}

    def scan_task16(self) -> Dict:
        """Task 16: 2 users with pet posts."""
        self.print_task_header(16, "2 Users with Pet Posts")

        keywords = ["猫", "猫咪", "宠物", "小狗", "小猫", "可爱", "萌宠", "宠物日常"]
        users = self.get_users_with_posts_containing(keywords, min_posts=1)

        print(f"  📊 Found {len(users)} users with matching posts\n")

        if len(users) >= 2:
            for i, user_data in enumerate(users[:2], 1):
                print(f"     {i}. {user_data['user']['name']} (ID: {user_data['user']['_id']}) - {user_data['match_count']} posts")

            # Print example post
            if users[0]["matching_posts"]:
                self.print_example_post(users[0]["matching_posts"][0])

            print("\n  ✅ PASS: Found 2+ users\n")
            return {"status": "PASS", "found": len(users), "required": 2, "users": users[:2]}
        else:
            print(f"\n  ❌ FAIL: Only found {len(users)} users (need 2)\n")
            return {"status": "FAIL", "found": len(users), "required": 2, "users": users}

    def scan_task17(self) -> Dict:
        """Task 17: 1 user with skincare posts."""
        self.print_task_header(17, "1 User with Skincare Posts")

        keywords = ["护肤", "保养", "面膜", "精华", "面霜", "routine", "步骤"]
        users = self.get_users_with_posts_containing(keywords, min_posts=1)

        print(f"  📊 Found {len(users)} users with matching posts\n")

        if len(users) >= 1:
            user_data = users[0]
            print(f"     1. {user_data['user']['name']} (ID: {user_data['user']['_id']}) - {user_data['match_count']} posts")

            # Print example post
            if user_data["matching_posts"]:
                self.print_example_post(user_data["matching_posts"][0])

            print("\n  ✅ PASS: Found 1+ users\n")
            return {"status": "PASS", "found": len(users), "required": 1, "users": users[:1]}
        else:
            print("\n  ❌ FAIL: No users found\n")
            return {"status": "FAIL", "found": 0, "required": 1, "users": []}

    def scan_task18(self) -> Dict:
        """Task 18: 1 trending topic about music + 2 related posts."""
        self.print_task_header(18, "1 Music Trending Topic + 2 Related Posts")

        keywords = ["音乐", "专辑", "新歌", "歌手", "演唱会", "单曲", "发行"]
        topics = self.get_trending_topics_with_keywords(keywords)

        print(f"  📊 Found {len(topics)} trending topics matching keywords\n")

        if topics:
            topic = topics[0]
            # Find posts related to music
            music_posts = [p for p in self.posts if self.post_matches_keywords(p, keywords)]

            print(f"  📌 Topic: {topic.get('text', 'N/A')}")
            print(f"  📝 Related music posts: {len(music_posts)}")

            if len(music_posts) >= 2:
                # Print example post
                self.print_example_post(music_posts[0])

                print("\n  ✅ PASS: Found topic with 2+ posts\n")
                return {"status": "PASS", "topic": topic, "posts": music_posts[:2]}
            else:
                print(f"\n  ⚠️  PARTIAL: Found topic but only {len(music_posts)} posts (need 2)\n")
                return {"status": "PARTIAL", "topic": topic, "posts": music_posts}
        else:
            print("\n  ❌ FAIL: No trending topics found\n")
            return {"status": "FAIL", "found": 0, "required": 1}

    def scan_task19(self) -> Dict:
        """Task 19: 1 account with food posts."""
        self.print_task_header(19, "1 Account with Food Posts")

        keywords = ["美食", "食物", "餐厅", "料理", "烹饪", "好吃", "推荐", "小吃", "菜谱"]
        users = self.get_users_with_posts_containing(keywords, min_posts=1)

        print(f"  📊 Found {len(users)} users with matching posts\n")

        if len(users) >= 1:
            user_data = users[0]
            print(f"     1. {user_data['user']['name']} (ID: {user_data['user']['_id']}) - {user_data['match_count']} posts")

            # Print example post
            if user_data["matching_posts"]:
                self.print_example_post(user_data["matching_posts"][0])

            print("\n  ✅ PASS: Found 1+ users\n")
            return {"status": "PASS", "found": len(users), "required": 1, "users": users[:1]}
        else:
            print("\n  ❌ FAIL: No users found\n")
            return {"status": "FAIL", "found": 0, "required": 1, "users": []}

    def scan_task21(self) -> Dict:
        """Task 21: 2 users with football posts."""
        self.print_task_header(21, "2 Users with Football Posts")

        keywords = ["足球", "世界杯", "比赛", "球员", "球队", "体育", "评论", "解说", "足球评论"]
        users = self.get_users_with_posts_containing(keywords, min_posts=1)

        print(f"  📊 Found {len(users)} users with matching posts\n")

        if len(users) >= 2:
            for i, user_data in enumerate(users[:2], 1):
                print(f"     {i}. {user_data['user']['name']} (ID: {user_data['user']['_id']}) - {user_data['match_count']} posts")

            # Print example post
            if users[0]["matching_posts"]:
                self.print_example_post(users[0]["matching_posts"][0])

            print("\n  ✅ PASS: Found 2+ users\n")
            return {"status": "PASS", "found": len(users), "required": 2, "users": users[:2]}
        else:
            print(f"\n  ❌ FAIL: Only found {len(users)} users (need 2)\n")
            return {"status": "FAIL", "found": len(users), "required": 2, "users": users}

    def scan_task23(self) -> Dict:
        """Task 23: 1 user with travel posts."""
        self.print_task_header(23, "1 User with Travel Posts")

        keywords = ["旅行", "旅游", "目的地", "景点", "游记", "攻略", "旅行计划"]
        users = self.get_users_with_posts_containing(keywords, min_posts=1)

        print(f"  📊 Found {len(users)} users with matching posts\n")

        if len(users) >= 1:
            user_data = users[0]
            print(f"     1. {user_data['user']['name']} (ID: {user_data['user']['_id']}) - {user_data['match_count']} posts")

            # Print example post
            if user_data["matching_posts"]:
                self.print_example_post(user_data["matching_posts"][0])

            print("\n  ✅ PASS: Found 1+ users\n")
            return {"status": "PASS", "found": len(users), "required": 1, "users": users[:1]}
        else:
            print("\n  ❌ FAIL: No users found\n")
            return {"status": "FAIL", "found": 0, "required": 1, "users": []}

    def scan_task24(self) -> Dict:
        """Task 24: 2 users with gaming posts."""
        self.print_task_header(24, "2 Users with Gaming Posts")

        keywords = ["游戏", "电竞", "玩家", "游戏攻略", "游戏直播"]
        users = self.get_users_with_posts_containing(keywords, min_posts=1)

        print(f"  📊 Found {len(users)} users with matching posts\n")

        if len(users) >= 2:
            for i, user_data in enumerate(users[:2], 1):
                print(f"     {i}. {user_data['user']['name']} (ID: {user_data['user']['_id']}) - {user_data['match_count']} posts")

            # Print example post
            if users[0]["matching_posts"]:
                self.print_example_post(users[0]["matching_posts"][0])

            print("\n  ✅ PASS: Found 2+ users\n")
            return {"status": "PASS", "found": len(users), "required": 2, "users": users[:2]}
        else:
            print(f"\n  ❌ FAIL: Only found {len(users)} users (need 2)\n")
            return {"status": "FAIL", "found": len(users), "required": 2, "users": users}

    def scan_task26(self) -> Dict:
        """Task 26: 1 trending topic about EVs + 1 post."""
        self.print_task_header(26, "1 EV Trending Topic + 1 Post")

        keywords = ["电动车", "新能源", "新能源汽车", "充电", "充电桩", "电动汽车"]
        topics = self.get_trending_topics_with_keywords(keywords)

        print(f"  📊 Found {len(topics)} trending topics matching keywords\n")

        if topics:
            topic = topics[0]
            # Find posts related to EVs
            ev_posts = [p for p in self.posts if self.post_matches_keywords(p, keywords)]

            print(f"  📌 Topic: {topic.get('text', 'N/A')}")
            print(f"  📝 Related EV posts: {len(ev_posts)}")

            if len(ev_posts) >= 1:
                # Print example post
                self.print_example_post(ev_posts[0])

                print("\n  ✅ PASS: Found topic with 1+ posts\n")
                return {"status": "PASS", "topic": topic, "posts": ev_posts[:1]}
            else:
                print("\n  ⚠️  PARTIAL: Found topic but no posts\n")
                return {"status": "PARTIAL", "topic": topic, "posts": []}
        else:
            print("\n  ❌ FAIL: No trending topics found\n")
            return {"status": "FAIL", "found": 0, "required": 1}

    def scan_task27(self) -> Dict:
        """Task 27: 1 account with in-depth analysis posts."""
        self.print_task_header(27, "1 Account with In-depth Analysis Posts")

        keywords = ["深度", "分析", "经验", "干货", "分享", "教程", "心得"]
        users = self.get_users_with_posts_containing(keywords, min_posts=1)

        print(f"  📊 Found {len(users)} users with matching posts\n")

        if len(users) >= 1:
            user_data = users[0]
            print(f"     1. {user_data['user']['name']} (ID: {user_data['user']['_id']}) - {user_data['match_count']} posts")

            # Print example post
            if user_data["matching_posts"]:
                self.print_example_post(user_data["matching_posts"][0])

            print("\n  ✅ PASS: Found 1+ users\n")
            return {"status": "PASS", "found": len(users), "required": 1, "users": users[:1]}
        else:
            print("\n  ❌ FAIL: No users found\n")
            return {"status": "FAIL", "found": 0, "required": 1, "users": []}

    def scan_task28(self) -> Dict:
        """Task 28: 2 users with home decor posts."""
        self.print_task_header(28, "2 Users with Home Decor Posts")

        keywords = ["家居", "装修", "室内设计", "家装", "ins风", "北欧风", "客厅", "卧室", "布置", "设计"]
        users = self.get_users_with_posts_containing(keywords, min_posts=1)

        print(f"  📊 Found {len(users)} users with matching posts\n")

        if len(users) >= 2:
            for i, user_data in enumerate(users[:2], 1):
                print(f"     {i}. {user_data['user']['name']} (ID: {user_data['user']['_id']}) - {user_data['match_count']} posts")

            # Print example post
            if users[0]["matching_posts"]:
                self.print_example_post(users[0]["matching_posts"][0])

            print("\n  ✅ PASS: Found 2+ users\n")
            return {"status": "PASS", "found": len(users), "required": 2, "users": users[:2]}
        else:
            print(f"\n  ❌ FAIL: Only found {len(users)} users (need 2)\n")
            return {"status": "FAIL", "found": len(users), "required": 2, "users": users}

    def scan_task29(self) -> Dict:
        """Task 29: 1 trending topic about entertainment + 2 posts."""
        self.print_task_header(29, "1 Entertainment Trending Topic + 2 Posts")

        keywords = ["娱乐", "综艺", "电视剧", "偶像", "明星", "艺人", "演员", "影视", "娱乐圈"]
        topics = self.get_trending_topics_with_keywords(keywords)

        print(f"  📊 Found {len(topics)} trending topics matching keywords\n")

        if topics:
            topic = topics[0]
            # Find posts related to entertainment
            ent_posts = [p for p in self.posts if self.post_matches_keywords(p, keywords)]

            print(f"  📌 Topic: {topic.get('text', 'N/A')}")
            print(f"  📝 Related entertainment posts: {len(ent_posts)}")

            if len(ent_posts) >= 2:
                # Print example post
                self.print_example_post(ent_posts[0])

                print("\n  ✅ PASS: Found topic with 2+ posts\n")
                return {"status": "PASS", "topic": topic, "posts": ent_posts[:2]}
            else:
                print(f"\n  ⚠️  PARTIAL: Found topic but only {len(ent_posts)} posts (need 2)\n")
                return {"status": "PARTIAL", "topic": topic, "posts": ent_posts}
        else:
            print("\n  ❌ FAIL: No trending topics found\n")
            return {"status": "FAIL", "found": 0, "required": 1}

    def scan_task30(self) -> Dict:
        """Task 30: 2 users with finance/stock posts."""
        self.print_task_header(30, "2 Users with Finance/Stock Posts")

        keywords = ["股票", "A股", "美股", "基金", "财经", "经济", "通胀", "利率", "投资", "理财", "金融", "股市", "证券"]
        users = self.get_users_with_posts_containing(keywords, min_posts=1)

        print(f"  📊 Found {len(users)} users with matching posts\n")

        if len(users) >= 2:
            for i, user_data in enumerate(users[:2], 1):
                print(f"     {i}. {user_data['user']['name']} (ID: {user_data['user']['_id']}) - {user_data['match_count']} posts")

            # Print example post
            if users[0]["matching_posts"]:
                self.print_example_post(users[0]["matching_posts"][0])

            print("\n  ✅ PASS: Found 2+ users\n")
            return {"status": "PASS", "found": len(users), "required": 2, "users": users[:2]}
        else:
            print(f"\n  ❌ FAIL: Only found {len(users)} users (need 2)\n")
            return {"status": "FAIL", "found": len(users), "required": 2, "users": users}

    def scan_task31(self) -> Dict:
        """Task 31: 2 posts from other users about food."""
        self.print_task_header(31, "2 Food Posts from Other Users")

        keywords = ["美食", "食物", "餐厅", "料理", "烹饪", "好吃", "推荐", "小吃", "菜谱", "探店", "美食推荐", "晚餐", "午餐", "早餐", "吃饭", "用餐", "菜品", "服务"]
        matching_posts = [p for p in self.posts if self.post_matches_keywords(p, keywords)]

        print(f"  📊 Found {len(matching_posts)} posts matching keywords\n")

        if len(matching_posts) >= 2:
            for i, post in enumerate(matching_posts[:2], 1):
                user_name = post.get("user", {}).get("name", "Unknown")
                content_preview = post.get("content", "")[:50]
                print(f"     {i}. {user_name}: {content_preview}...")

            # Print example post
            self.print_example_post(matching_posts[0])

            print("\n  ✅ PASS: Found 2+ posts\n")
            return {"status": "PASS", "found": len(matching_posts), "required": 2, "posts": matching_posts[:2]}
        else:
            print(f"\n  ❌ FAIL: Only found {len(matching_posts)} posts (need 2)\n")
            return {"status": "FAIL", "found": len(matching_posts), "required": 2, "posts": matching_posts}

    def scan_task32(self) -> Dict:
        """Task 32: 2 users with comedy/humor posts."""
        self.print_task_header(32, "2 Users with Comedy/Humor Posts")

        keywords = ["搞笑", "段子", "幽默", "笑话", "喜剧", "有趣", "好玩", "逗比", "娱乐", "开心"]
        users = self.get_users_with_posts_containing(keywords, min_posts=1)

        print(f"  📊 Found {len(users)} users with matching posts\n")

        if len(users) >= 2:
            for i, user_data in enumerate(users[:2], 1):
                print(f"     {i}. {user_data['user']['name']} (ID: {user_data['user']['_id']}) - {user_data['match_count']} posts")

            # Print example post
            if users[0]["matching_posts"]:
                self.print_example_post(users[0]["matching_posts"][0])

            print("\n  ✅ PASS: Found 2+ users\n")
            return {"status": "PASS", "found": len(users), "required": 2, "users": users[:2]}
        else:
            print(f"\n  ❌ FAIL: Only found {len(users)} users (need 2)\n")
            return {"status": "FAIL", "found": len(users), "required": 2, "users": users}

    def scan_task33(self) -> Dict:
        """Task 33: 2 users with fitness/health posts."""
        self.print_task_header(33, "2 Users with Fitness/Health Posts")

        keywords = ["健身", "运动", "健康", "锻炼", "训练", "瑜伽", "跑步", "减肥", "增肌", "营养", "体脂", "肌肉"]
        users = self.get_users_with_posts_containing(keywords, min_posts=1)

        print(f"  📊 Found {len(users)} users with matching posts\n")

        if len(users) >= 2:
            for i, user_data in enumerate(users[:2], 1):
                print(f"     {i}. {user_data['user']['name']} (ID: {user_data['user']['_id']}) - {user_data['match_count']} posts")

            # Print example post
            if users[0]["matching_posts"]:
                self.print_example_post(users[0]["matching_posts"][0])

            print("\n  ✅ PASS: Found 2+ users\n")
            return {"status": "PASS", "found": len(users), "required": 2, "users": users[:2]}
        else:
            print(f"\n  ❌ FAIL: Only found {len(users)} users (need 2)\n")
            return {"status": "FAIL", "found": len(users), "required": 2, "users": users}

    def scan_task34(self) -> Dict:
        """Task 34: 1 trending topic about smartphones + 1 post with comments."""
        self.print_task_header(34, "1 Smartphone Trending Topic + 1 Post with Comments")

        keywords = ["手机", "智能手机", "新品", "发布", "发布会", "科技", "数码", "iPhone", "华为", "小米", "OPPO", "vivo", "旗舰", "配置"]
        topics = self.get_trending_topics_with_keywords(keywords)

        print(f"  📊 Found {len(topics)} trending topics matching keywords\n")

        if topics:
            topic = topics[0]
            # Find posts related to smartphones with comments
            phone_posts = [p for p in self.posts if self.post_matches_keywords(p, keywords)]
            posts_with_comments = [p for p in phone_posts if len(self.comments_by_post.get(p["_id"], [])) > 0]

            print(f"  📌 Topic: {topic.get('text', 'N/A')}")
            print(f"  📝 Related phone posts: {len(phone_posts)}")
            print(f"  💬 Posts with comments: {len(posts_with_comments)}")

            if len(posts_with_comments) >= 1:
                # Print example post
                self.print_example_post(posts_with_comments[0])

                print("\n  ✅ PASS: Found topic with 1+ posts with comments\n")
                return {"status": "PASS", "topic": topic, "posts": posts_with_comments[:1]}
            else:
                print(f"\n  ⚠️  PARTIAL: Found topic but no posts with comments\n")
                return {"status": "PARTIAL", "topic": topic, "posts": phone_posts[:1] if phone_posts else []}
        else:
            print("\n  ❌ FAIL: No trending topics found\n")
            return {"status": "FAIL", "found": 0, "required": 1}

    def scan_task35(self) -> Dict:
        """Task 35: 2 users with illustration/art posts + 2 posts."""
        self.print_task_header(35, "2 Users with Illustration/Art Posts + 2 Posts")

        keywords = ["插画", "绘画", "艺术", "设计", "手绘", "数字艺术", "illustration", "art", "作品", "创作", "风格", "画风", "插画师", "艺术家", "设计师"]
        users = self.get_users_with_posts_containing(keywords, min_posts=1)

        # Get posts matching keywords
        art_posts = [p for p in self.posts if self.post_matches_keywords(p, keywords)]

        print(f"  📊 Found {len(users)} users with matching posts")
        print(f"  📊 Found {len(art_posts)} total art posts\n")

        if len(users) >= 2 and len(art_posts) >= 2:
            for i, user_data in enumerate(users[:2], 1):
                print(f"     {i}. {user_data['user']['name']} (ID: {user_data['user']['_id']}) - {user_data['match_count']} posts")

            # Print example post
            self.print_example_post(art_posts[0])

            print("\n  ✅ PASS: Found 2+ users and 2+ posts\n")
            return {"status": "PASS", "found_users": len(users), "found_posts": len(art_posts), "users": users[:2], "posts": art_posts[:2]}
        elif len(users) >= 2:
            print(f"\n  ⚠️  PARTIAL: Found 2+ users but only {len(art_posts)} posts\n")
            return {"status": "PARTIAL", "found_users": len(users), "found_posts": len(art_posts), "users": users[:2], "posts": art_posts}
        else:
            print(f"\n  ❌ FAIL: Only found {len(users)} users and {len(art_posts)} posts\n")
            return {"status": "FAIL", "found_users": len(users), "found_posts": len(art_posts), "users": users, "posts": art_posts}

    def scan_task37(self) -> Dict:
        """Task 37: 2 users with coffee posts."""
        self.print_task_header(37, "2 Users with Coffee Posts")

        keywords = ["咖啡", "手冲", "拉花", "咖啡店", "cafe", "brewing", "咖啡豆", "咖啡师", "咖啡推荐", "咖啡文化", "咖啡器具", "咖啡评测"]
        users = self.get_users_with_posts_containing(keywords, min_posts=1)

        print(f"  📊 Found {len(users)} users with matching posts\n")

        if len(users) >= 2:
            for i, user_data in enumerate(users[:2], 1):
                print(f"     {i}. {user_data['user']['name']} (ID: {user_data['user']['_id']}) - {user_data['match_count']} posts")

            # Print example post
            if users[0]["matching_posts"]:
                self.print_example_post(users[0]["matching_posts"][0])

            print("\n  ✅ PASS: Found 2+ users\n")
            return {"status": "PASS", "found": len(users), "required": 2, "users": users[:2]}
        else:
            print(f"\n  ❌ FAIL: Only found {len(users)} users (need 2)\n")
            return {"status": "FAIL", "found": len(users), "required": 2, "users": users}

    def scan_task39(self) -> Dict:
        """Task 39: 1 trending topic about anime + 2 posts."""
        self.print_task_header(39, "1 Anime Trending Topic + 2 Posts")

        keywords = ["动漫", "动画", "anime", "番剧", "新番", "二次元", "角色", "剧情", "OP", "ED", "声优", "制作", "更新"]
        topics = self.get_trending_topics_with_keywords(keywords)

        print(f"  📊 Found {len(topics)} trending topics matching keywords\n")

        if topics:
            topic = topics[0]
            # Find posts related to anime
            anime_posts = [p for p in self.posts if self.post_matches_keywords(p, keywords)]

            print(f"  📌 Topic: {topic.get('text', 'N/A')}")
            print(f"  📝 Related anime posts: {len(anime_posts)}")

            if len(anime_posts) >= 2:
                # Print example post
                self.print_example_post(anime_posts[0])

                print("\n  ✅ PASS: Found topic with 2+ posts\n")
                return {"status": "PASS", "topic": topic, "posts": anime_posts[:2]}
            else:
                print(f"\n  ⚠️  PARTIAL: Found topic but only {len(anime_posts)} posts (need 2)\n")
                return {"status": "PARTIAL", "topic": topic, "posts": anime_posts}
        else:
            # No trending topic, but check if we have posts
            anime_posts = [p for p in self.posts if self.post_matches_keywords(p, keywords)]
            print(f"  No trending topics, but found {len(anime_posts)} anime posts")

            if len(anime_posts) >= 2:
                print(f"\n  ⚠️  PARTIAL: No trending topic but found 2+ posts\n")
                return {"status": "PARTIAL", "topic": None, "posts": anime_posts[:2]}
            else:
                print("\n  ❌ FAIL: No trending topics found\n")
                return {"status": "FAIL", "found": 0, "required": 1}

    def scan_task40(self) -> Dict:
        """Task 40: 1 custom group about news + 2 users with news posts."""
        self.print_task_header(40, "1 News Custom Group + 2 Users with News Posts")

        group_keywords = ["新闻", "资讯", "媒体", "记者", "news", "journalism", "新闻资讯"]
        post_keywords = ["新闻", "报道", "记者", "媒体", "资讯", "news", "journalism", "采访", "时事", "热点", "深度", "分析"]

        groups = self.get_custom_groups_with_name(group_keywords)
        users = self.get_users_with_posts_containing(post_keywords, min_posts=1)

        print(f"  📊 Found {len(groups)} custom groups matching keywords")
        print(f"  📊 Found {len(users)} users with news posts\n")

        if len(groups) >= 1 and len(users) >= 2:
            print(f"  👥 Group: {groups[0].get('name', 'N/A')}")
            for i, user_data in enumerate(users[:2], 1):
                print(f"     {i}. {user_data['user']['name']} (ID: {user_data['user']['_id']}) - {user_data['match_count']} posts")

            # Print example post
            if users[0]["matching_posts"]:
                self.print_example_post(users[0]["matching_posts"][0])

            print("\n  ✅ PASS: Found group with 2+ users\n")
            return {"status": "PASS", "group": groups[0], "users": users[:2]}
        elif len(groups) >= 1:
            print(f"\n  ⚠️  PARTIAL: Found group but only {len(users)} users (need 2)\n")
            return {"status": "PARTIAL", "group": groups[0], "users": users}
        else:
            print(f"\n  ❌ FAIL: No custom groups found (found {len(users)} users)\n")
            return {"status": "FAIL", "found_groups": 0, "found_users": len(users)}

    def scan_task41(self) -> Dict:
        """Task 41: 2 users with beach/travel posts."""
        self.print_task_header(41, "2 Users with Beach/Travel Posts")

        keywords = ["海边", "度假", "海滩", "旅行", "旅游", "beach", "travel", "攻略", "推荐", "景点", "路线", "住宿", "tips"]
        users = self.get_users_with_posts_containing(keywords, min_posts=1)

        print(f"  📊 Found {len(users)} users with matching posts\n")

        if len(users) >= 2:
            for i, user_data in enumerate(users[:2], 1):
                print(f"     {i}. {user_data['user']['name']} (ID: {user_data['user']['_id']}) - {user_data['match_count']} posts")

            # Print example post
            if users[0]["matching_posts"]:
                self.print_example_post(users[0]["matching_posts"][0])

            print("\n  ✅ PASS: Found 2+ users\n")
            return {"status": "PASS", "found": len(users), "required": 2, "users": users[:2]}
        else:
            print(f"\n  ❌ FAIL: Only found {len(users)} users (need 2)\n")
            return {"status": "FAIL", "found": len(users), "required": 2, "users": users}

    def scan_task42(self) -> Dict:
        """Task 42: 1 post from another user about concerts."""
        self.print_task_header(42, "1 Concert Post from Another User")

        keywords = ["演唱会", "音乐会", "concert", "演出", "现场", "音乐", "歌手", "artist", "live", "表演"]
        matching_posts = [p for p in self.posts if self.post_matches_keywords(p, keywords)]

        print(f"  📊 Found {len(matching_posts)} posts matching keywords\n")

        if len(matching_posts) >= 1:
            post = matching_posts[0]
            user_name = post.get("user", {}).get("name", "Unknown")
            content_preview = post.get("content", "")[:50]
            print(f"     1. {user_name}: {content_preview}...")
            print("\n  ✅ PASS: Found 1+ posts\n")
            return {"status": "PASS", "found": len(matching_posts), "required": 1, "posts": matching_posts[:1]}
        else:
            print("\n  ❌ FAIL: No posts found\n")
            return {"status": "FAIL", "found": 0, "required": 1, "posts": []}

    def scan_task43(self) -> Dict:
        """Task 43: 2 fashion posts in feed + 1 user with fashion posts."""
        self.print_task_header(43, "2 Fashion Posts in Feed + 1 User with Fashion Posts")

        keywords = ["时尚", "穿搭", "fashion", "style", "搭配", "服装", "服饰", "造型", "look", "ootd", "outfit", "风格", "潮流"]

        # Find posts in main feed
        fashion_posts = [p for p in self.posts if self.post_matches_keywords(p, keywords)]

        # Find users with fashion posts
        users = self.get_users_with_posts_containing(keywords, min_posts=1)

        print(f"  📊 Found {len(fashion_posts)} fashion posts in feed")
        print(f"  📊 Found {len(users)} users with fashion posts\n")

        if len(fashion_posts) >= 2 and len(users) >= 1:
            for i, post in enumerate(fashion_posts[:2], 1):
                user_name = post.get("user", {}).get("name", "Unknown")
                content_preview = post.get("content", "")[:50]
                print(f"     Post {i}. {user_name}: {content_preview}...")
            user_data = users[0]
            print(f"     User: {user_data['user']['name']} (ID: {user_data['user']['_id']}) - {user_data['match_count']} posts")

            # Print example post
            self.print_example_post(fashion_posts[0])

            print("\n  ✅ PASS: Found 2+ posts and 1+ users\n")
            return {"status": "PASS", "posts": fashion_posts[:2], "users": users[:1]}
        else:
            print(f"\n  ❌ FAIL: Only found {len(fashion_posts)} posts and {len(users)} users\n")
            return {"status": "FAIL", "found_posts": len(fashion_posts), "found_users": len(users)}

    def scan_task44(self) -> Dict:
        """Task 44: 1 user with parenting posts."""
        self.print_task_header(44, "1 User with Parenting Posts")

        keywords = ["育儿", "亲子", "妈妈", "parenting", "儿童", "宝宝", "教育", "成长", "带娃", "育儿经验", "亲子活动"]
        users = self.get_users_with_posts_containing(keywords, min_posts=1)

        print(f"  📊 Found {len(users)} users with matching posts\n")

        if len(users) >= 1:
            user_data = users[0]
            print(f"     1. {user_data['user']['name']} (ID: {user_data['user']['_id']}) - {user_data['match_count']} posts")

            # Print example post
            if user_data["matching_posts"]:
                self.print_example_post(user_data["matching_posts"][0])

            print("\n  ✅ PASS: Found 1+ users\n")
            return {"status": "PASS", "found": len(users), "required": 1, "users": users[:1]}
        else:
            print("\n  ❌ FAIL: No users found\n")
            return {"status": "FAIL", "found": 0, "required": 1, "users": []}

    def scan_task45(self) -> Dict:
        """Task 45: 1 trending topic about movies + 3 recommendation posts."""
        self.print_task_header(45, "1 Movie Trending Topic + 3 Recommendation Posts")

        topic_keywords = ["电影", "影片", "movie", "film", "cinema", "影院", "影评", "电影推荐"]
        rec_keywords = ["推荐", "好看", "值得看", "必看", "建议", "值得", "不错", "推荐看"]

        topics = self.get_trending_topics_with_keywords(topic_keywords)

        # Find posts about movies that also contain recommendation keywords
        movie_posts = [p for p in self.posts if self.post_matches_keywords(p, topic_keywords)]
        rec_posts = [p for p in movie_posts if self.contains_any_keyword(p.get("content", ""), rec_keywords)]

        print(f"  📊 Found {len(topics)} trending topics matching keywords")
        print(f"  📝 Found {len(movie_posts)} movie posts")
        print(f"  ⭐ Found {len(rec_posts)} movie recommendation posts\n")

        if len(topics) >= 1 and len(rec_posts) >= 3:
            topic = topics[0]
            print(f"  📌 Topic: {topic.get('text', 'N/A')}")
            for i, post in enumerate(rec_posts[:3], 1):
                user_name = post.get("user", {}).get("name", "Unknown")
                content_preview = post.get("content", "")[:50]
                print(f"     {i}. {user_name}: {content_preview}...")

            # Print example post
            self.print_example_post(rec_posts[0])

            print("\n  ✅ PASS: Found topic with 3+ recommendation posts\n")
            return {"status": "PASS", "topic": topic, "posts": rec_posts[:3]}
        elif len(topics) >= 1:
            print(f"\n  ⚠️  PARTIAL: Found topic but only {len(rec_posts)} recommendation posts (need 3)\n")
            return {"status": "PARTIAL", "topic": topics[0], "posts": rec_posts}
        else:
            print(f"\n  ❌ FAIL: No trending topics found (found {len(rec_posts)} recommendation posts)\n")
            return {"status": "FAIL", "found": 0, "required": 1}

    def scan_task47(self) -> Dict:
        """Task 47: 2 users with photography tutorial posts."""
        self.print_task_header(47, "2 Users with Photography Tutorial Posts")

        photo_keywords = ["摄影", "拍照", "photography", "相机", "镜头", "构图", "光线"]
        tutorial_keywords = ["摄影技巧", "摄影教程", "photography tutorial", "摄影教学", "教程", "技巧", "教学", "如何", "方法", "步骤", "分享", "经验"]

        # Find users with photography posts
        photo_users = self.get_users_with_posts_containing(photo_keywords, min_posts=1)

        # Filter to only users whose posts also contain tutorial keywords
        tutorial_users = []
        for user_data in photo_users:
            tutorial_posts = [p for p in user_data["matching_posts"]
                            if self.contains_any_keyword(p.get("content", ""), tutorial_keywords)]
            if tutorial_posts:
                tutorial_users.append({
                    "user": user_data["user"],
                    "matching_posts": tutorial_posts,
                    "match_count": len(tutorial_posts)
                })

        print(f"  📊 Found {len(tutorial_users)} users with photography tutorial posts\n")

        if len(tutorial_users) >= 2:
            for i, user_data in enumerate(tutorial_users[:2], 1):
                print(f"     {i}. {user_data['user']['name']} (ID: {user_data['user']['_id']}) - {user_data['match_count']} posts")
            print("\n  ✅ PASS: Found 2+ users\n")
            return {"status": "PASS", "found": len(tutorial_users), "required": 2, "users": tutorial_users[:2]}
        else:
            print(f"\n  ❌ FAIL: Only found {len(tutorial_users)} users (need 2)\n")
            return {"status": "FAIL", "found": len(tutorial_users), "required": 2, "users": tutorial_users}

    def scan_task48(self) -> Dict:
        """Task 48: 1 user with lifestyle/vlog posts."""
        self.print_task_header(48, "1 User with Lifestyle/Vlog Posts")

        keywords = ["生活", "lifestyle", "生活方式", "日常", "生活分享", "vlog", "日常分享", "生活记录", "日常vlog", "生活vlog"]
        users = self.get_users_with_posts_containing(keywords, min_posts=1)

        print(f"  📊 Found {len(users)} users with matching posts\n")

        if len(users) >= 1:
            user_data = users[0]
            print(f"     1. {user_data['user']['name']} (ID: {user_data['user']['_id']}) - {user_data['match_count']} posts")

            # Print example post
            if user_data["matching_posts"]:
                self.print_example_post(user_data["matching_posts"][0])

            print("\n  ✅ PASS: Found 1+ users\n")
            return {"status": "PASS", "found": len(users), "required": 1, "users": users[:1]}
        else:
            print("\n  ❌ FAIL: No users found\n")
            return {"status": "FAIL", "found": 0, "required": 1, "users": []}

    def print_summary(self, results: Dict):
        """Print summary of all task results."""
        passed = sum(1 for r in results.values() if r.get("status") == "PASS")
        partial = sum(1 for r in results.values() if r.get("status") == "PARTIAL")
        failed = sum(1 for r in results.values() if r.get("status") == "FAIL")
        total = len(results)

        print("\n" + "=" * 70)
        print("📈 SUMMARY".center(70))
        print("=" * 70)

        print(f"\n  📊 Total Tasks:  {total}")
        print(f"  ✅ Passed:       {passed:2d} ({passed/total*100:5.1f}%)")
        print(f"  ⚠️  Partial:      {partial:2d} ({partial/total*100:5.1f}%)")
        print(f"  ❌ Failed:       {failed:2d} ({failed/total*100:5.1f}%)")

        print("\n" + "-" * 70)
        print("  TASK BREAKDOWN")
        print("-" * 70 + "\n")

        # Group results by status for better readability
        passed_tasks = []
        partial_tasks = []
        failed_tasks = []

        for task_num in sorted([int(k.replace('task', '')) for k in results.keys()]):
            task_key = f'task{task_num}'
            result = results[task_key]
            status = result.get("status", "UNKNOWN")

            if status == "PASS":
                passed_tasks.append(task_num)
            elif status == "PARTIAL":
                partial_tasks.append(task_num)
            else:
                failed_tasks.append(task_num)

        if passed_tasks:
            print(f"  ✅ PASSED ({len(passed_tasks)}):")
            for i, task_num in enumerate(passed_tasks, 1):
                if i % 10 == 1 and i > 1:
                    print()
                print(f"     Task {task_num:2d}", end="  ")
            print("\n")

        if partial_tasks:
            print(f"  ⚠️  PARTIAL ({len(partial_tasks)}):")
            for i, task_num in enumerate(partial_tasks, 1):
                if i % 10 == 1 and i > 1:
                    print()
                print(f"     Task {task_num:2d}", end="  ")
            print("\n")

        if failed_tasks:
            print(f"  ❌ FAILED ({len(failed_tasks)}):")
            for i, task_num in enumerate(failed_tasks, 1):
                if i % 10 == 1 and i > 1:
                    print()
                print(f"     Task {task_num:2d}", end="  ")
            print("\n")

        print("=" * 70)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Scan Weibo data to check task requirements"
    )
    parser.add_argument(
        "file",
        type=Path,
        help="Path to the weibo initial_data.json file to analyze"
    )
    args = parser.parse_args()

    data_file = args.file

    # Check if file exists
    if not data_file.exists():
        print(f"Error: File not found: {data_file}")
        return 1

    # Load data
    with open(data_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Create scanner and run all scans
    scanner = TaskScanner(data)
    results = scanner.scan_all_tasks()

    # Print summary
    scanner.print_summary(results)

    # Save detailed results to file
    output_file = data_file.parent / "task_scan_results.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\nDetailed results saved to: {output_file}")


if __name__ == "__main__":
    main()
