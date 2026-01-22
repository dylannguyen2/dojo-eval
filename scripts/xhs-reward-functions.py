"""
Reward functions for Xiaohongshu generated tasks.

This file contains reward functions for the 50 generated tasks from xhs-generated-tasks.json.
Each task has both backend and frontend validation functions following the V2 architecture pattern.
"""

import logging
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Optional, Tuple, TypedDict

logger = logging.getLogger(__name__)

# =============================================================================
# Type Definitions
# =============================================================================

class StateKeyQuery(TypedDict):
    collection: str
    filter: Dict[str, Any]


StateKey = Dict[str, StateKeyQuery]
ValidatorFunc = Callable[[Dict[str, Any]], Tuple[float, str]]


class ValidateTask(TypedDict):
    state_key: StateKey
    validate: Callable[[Backend, Dict[str, Any]], Tuple[float, str]]


# =============================================================================
# Backend Query Interface
# =============================================================================

class Backend(ABC):
    @abstractmethod
    def query(self, query: dict[str, Any]) -> Any:
        """Execute a MongoDB query.
        
        Args:
            query: A dict with 'collection' and 'filter' keys, e.g.
                   {"collection": "userFollows", "filter": {}}
        """
        pass


class BackendDictAdapter(Backend):
    """Adapter to wrap backend state dict as a Backend object."""

    def __init__(self, backend_state: Dict[str, Any]):
        self.backend_state = backend_state

    def query(self, query: dict[str, Any]) -> Any:
        """Query backend state dict."""
        collection = query.get("collection")
        filter_dict = query.get("filter", {})

        if collection not in self.backend_state:
            return []

        items = self.backend_state[collection]
        if not isinstance(items, list):
            return []

        # Simple filter matching
        filtered = []
        for item in items:
            if isinstance(item, dict):
                match = True
                for key, value in filter_dict.items():
                    if item.get(key) != value:
                        match = False
                        break
                if match:
                    filtered.append(item)

        return filtered


# =============================================================================
# Helper Functions
# =============================================================================

def _get_current_user(backend: Backend, current_user_id: str) -> Dict[str, Any]:
    """Get current user from backend."""
    users = backend.query({"collection": "users", "filter": {"_id": current_user_id}})
    if not users:
        raise ValueError(f"User {current_user_id} not found")
    return users[0]


def _get_post(backend: Backend, post_id: str) -> Dict[str, Any]:
    """Get post from backend."""
    posts = backend.query({"collection": "posts", "filter": {"_id": post_id}})
    if not posts:
        raise ValueError(f"Post {post_id} not found")
    return posts[0]


def _get_user(backend: Backend, user_id: str) -> Dict[str, Any]:
    """Get user from backend."""
    users = backend.query({"collection": "users", "filter": {"_id": user_id}})
    if not users:
        raise ValueError(f"User {user_id} not found")
    return users[0]


def _check_topic_relevance(
    post: Dict[str, Any], topic_area: str, keywords: Optional[List[str]] = None
) -> bool:
    """Check if a post is relevant to a topic area."""
    if keywords is None:
        # Default keywords for common topic areas
        topic_keywords = {
            "fitness": ["fitness", "workout", "exercise", "gym", "training", "运动", "健身", "锻炼", "运动健身", "健身运动", "减脂", "增肌", "瑜伽", "跑步", "健身教练"],
            "beauty": ["beauty", "makeup", "skincare", "cosmetic", "美容", "化妆", "护肤", "美妆", "彩妆", "美甲", "发型", "美容护肤", "化妆品", "护肤品"],
            "food": ["food", "recipe", "cooking", "meal", "dining", "美食", "食谱", "烹饪", "料理", "菜谱", "做饭", "下厨", "餐厅", "小吃", "甜品", "烘焙", "家常菜"],
            "travel": ["travel", "trip", "vacation", "destination", "旅游", "旅行", "景点", "出游", "度假", "攻略", "游记", "自由行", "旅行攻略", "旅游攻略", "打卡"],
            "home": ["home", "interior", "decor", "furniture", "家居", "装修", "装饰", "家装", "室内", "家具", "收纳", "整理", "布置", "软装", "硬装"],
            "fashion": ["fashion", "outfit", "style", "clothing", "时尚", "穿搭", "服装", "搭配", "穿衣", "潮流", "时装", "服饰", "穿搭分享", "ootd"],
            "art": ["art", "drawing", "painting", "illustration", "艺术", "绘画", "插画", "画画", "手绘", "水彩", "油画", "素描", "创作", "设计", "艺术家"],
            "pets": ["pet", "dog", "cat", "animal", "宠物", "狗", "猫", "养宠", "萌宠", "宠物日常", "宠物用品", "宠物护理", "宠物训练"],
            "wellness": ["wellness", "meditation", "mindfulness", "wellbeing", "健康", "冥想", "养生", "保健", "身心健康", "心理健康", "放松", "减压", "瑜伽", "正念"],
            "lifestyle": ["lifestyle", "routine", "daily", "life", "生活方式", "日常", "生活", "日常分享", "生活记录", "生活vlog", "生活碎片"],
            "education": ["education", "study", "learning", "tutorial", "教育", "学习", "教程", "知识", "学习分享", "学习方法", "学习笔记", "读书", "阅读", "课程"],
            "settings": [],
            "general": [],
            "culture": ["book", "reading", "literature", "书籍", "阅读", "文学", "读书", "书单", "读后感", "文学作品", "小说", "阅读分享"],
        }
        keywords = topic_keywords.get(topic_area.lower(), [topic_area.lower()])

    title = (post.get("title", "") or "").lower()
    caption = (post.get("caption", "") or "").lower()
    tags = [tag.lower() for tag in post.get("tags", [])]
    location = (post.get("location", "") or "").lower()

    content = f"{title} {caption} {location} {' '.join(tags)}"
    return any(keyword.lower() in content for keyword in keywords)


def _check_user_category_relevance(
    user: Dict[str, Any], topic_area: str
) -> bool:
    """Check if a user's category is relevant to a topic area."""
    category = (user.get("category", "") or "").lower()
    bio = (user.get("bio", "") or "").lower()
    
    topic_keywords = {
        "fitness": ["fitness", "workout", "exercise", "gym", "运动", "健身", "锻炼", "运动健身", "健身运动", "减脂", "增肌", "瑜伽", "跑步", "健身教练"],
        "beauty": ["beauty", "makeup", "skincare", "cosmetic", "美容", "化妆", "护肤", "美妆", "彩妆", "美甲", "发型", "美容护肤", "化妆品", "护肤品"],
        "food": ["food", "recipe", "cooking", "chef", "美食", "食谱", "烹饪", "料理", "菜谱", "做饭", "下厨", "餐厅", "小吃", "甜品", "烘焙", "家常菜"],
        "travel": ["travel", "trip", "vacation", "旅游", "旅行", "景点", "出游", "度假", "攻略", "游记", "自由行", "旅行攻略", "旅游攻略", "打卡"],
        "home": ["home", "interior", "decor", "家居", "装修", "家装", "室内", "家具", "收纳", "整理", "布置", "软装", "硬装"],
        "fashion": ["fashion", "style", "outfit", "时尚", "穿搭", "搭配", "穿衣", "潮流", "时装", "服饰", "穿搭分享", "ootd"],
        "art": ["art", "drawing", "painting", "illustration", "艺术", "绘画", "插画", "画画", "手绘", "水彩", "油画", "素描", "创作", "设计", "艺术家"],
        "pets": ["pet", "dog", "cat", "animal", "宠物", "狗", "猫", "养宠", "萌宠", "宠物日常", "宠物用品", "宠物护理", "宠物训练"],
        "wellness": ["wellness", "meditation", "mindfulness", "健康", "冥想", "养生", "保健", "身心健康", "心理健康", "放松", "减压", "瑜伽", "正念"],
        "lifestyle": ["lifestyle", "routine", "生活方式", "日常", "生活", "日常分享", "生活记录", "生活vlog", "生活碎片"],
        "education": ["education", "study", "learning", "教育", "学习", "教程", "知识", "学习分享", "学习方法", "学习笔记", "读书", "阅读", "课程"],
        "settings": [],
        "general": [],
        "culture": ["book", "reading", "literature", "书籍", "阅读", "文学", "读书", "书单", "读后感", "文学作品", "小说", "阅读分享"],
    }
    keywords = topic_keywords.get(topic_area.lower(), [topic_area.lower()])
    
    return any(keyword in category or keyword in bio for keyword in keywords)


# =============================================================================
# Task 1: I'm starting a new fitness routine and need motivation. Find some workout posts ...
# =============================================================================

def _validate_starting_new_fitness_routine(
    final_state_backend: Backend, final_state_frontend: Dict[str, Any]
) -> Tuple[float, str]:
    """Validate I'm starting a new fitness routine and need motivation. Find...
    
    Initial State Assumptions:
    - currentUser.following is empty [] before task starts
    - currentUser.bookmarks is empty [] before task starts
    - currentUser.albums is empty [] before task starts
    """
    current_user_id = final_state_frontend.get("currentUserId", "0")
    if not current_user_id:
        return 0.0, "currentUserId missing in frontend state"
    
    try:
        current_user = _get_current_user(final_state_backend)
    except ValueError as e:
        return 0.0, str(e)
    
    # Check following count
    following = current_user.get("following", [])
    if not isinstance(following, list):
        return 0.0, "following is not a list"
    if len(following) < 2:
        return 0.0, f"Expected at least 2 followed user(s), got {len(following)}"
    
    # Check if followed users are fitness-related
    fitness_following_count = 0
    for user_id in following:
        try:
            user = _get_user(final_state_backend, user_id)
            if _check_user_category_relevance(user, "fitness"):
                fitness_following_count += 1
        except ValueError:
            continue
    
    if fitness_following_count < 2:
        return 0.0, f"Expected at least 2 fitness-related followed user(s), got {fitness_following_count}"

    # Check bookmarks count
    bookmarks = current_user.get("bookmarks", [])
    if not isinstance(bookmarks, list):
        return 0.0, "bookmarks is not a list"
    if len(bookmarks) < 3:
        return 0.0, f"Expected at least 3 bookmarked post(s), got {len(bookmarks)}"
    
    # Check if bookmarked posts are fitness-related
    fitness_bookmarks_count = 0
    for post_id in bookmarks:
        try:
            post = _get_post(final_state_backend, post_id)
            if _check_topic_relevance(post, "fitness"):
                fitness_bookmarks_count += 1
        except ValueError:
            continue
    
    if fitness_bookmarks_count < 3:
        return 0.0, f"Expected at least 3 fitness-related bookmarked posts, got {fitness_bookmarks_count}"

    # Check for album with at least 3 posts
    albums = current_user.get("albums", [])
    if not isinstance(albums, list):
        return 0.0, "albums is not a list"
    
    album_found = None
    for album in albums:
        post_ids = album.get("postIds", [])
        if isinstance(post_ids, list) and len(post_ids) >= 3:
            album_found = album
            break
    
    if not album_found:
        return 0.0, f"No album found with at least 3 posts"

    return 1.0, "Task completed successfully"


_validate_starting_new_fitness_routine: ValidateTask = {
    "state_key": {
        "users": {"collection": "users", "filter": {}},
        "posts": {"collection": "posts", "filter": {}},
    },
    "validate": _validate_starting_new_fitness_routine,
}


# =============================================================================
# Task 2: My friend recommended some beauty blogger but I can't remember her name—somethin...
# =============================================================================

def _validate_friend_recommended_some_beauty(
    final_state_backend: Backend, final_state_frontend: Dict[str, Any]
) -> Tuple[float, str]:
    """Validate My friend recommended some beauty blogger but I can't rememb...
    
    Initial State Assumptions:
    - currentUser.following is empty [] before task starts
    - currentUser.liked is empty [] before task starts
    """
    current_user_id = final_state_frontend.get("currentUserId", "0")
    if not current_user_id:
        return 0.0, "currentUserId missing in frontend state"
    
    try:
        current_user = _get_current_user(final_state_backend)
    except ValueError as e:
        return 0.0, str(e)
    
    profile_view = final_state_frontend.get("profileView")
    if profile_view != "likes":
        return 0.0, f"Expected profileView='likes', got '{profile_view}'"

    # Check following count
    following = current_user.get("following", [])
    if not isinstance(following, list):
        return 0.0, "following is not a list"
    if len(following) < 1:
        return 0.0, f"Expected at least 1 followed user(s), got {len(following)}"
    
    # Check if followed users are beauty-related
    beauty_following_count = 0
    for user_id in following:
        try:
            user = _get_user(final_state_backend, user_id)
            if _check_user_category_relevance(user, "beauty"):
                beauty_following_count += 1
        except ValueError:
            continue
    
    if beauty_following_count < 1:
        return 0.0, f"Expected at least 1 beauty-related followed user(s), got {beauty_following_count}"

    # Check liked posts count
    liked = current_user.get("liked", [])
    if not isinstance(liked, list):
        return 0.0, "liked is not a list"
    if len(liked) < 2:
        return 0.0, f"Expected at least 2 liked post(s), got {len(liked)}"
    
    # Check if liked posts are beauty-related
    beauty_liked_count = 0
    for post_id in liked:
        try:
            post = _get_post(final_state_backend, post_id)
            if _check_topic_relevance(post, "beauty"):
                beauty_liked_count += 1
        except ValueError:
            continue
    
    if beauty_liked_count < 2:
        return 0.0, f"Expected at least 2 beauty-related liked posts, got {beauty_liked_count}"

    return 1.0, "Task completed successfully"


_validate_friend_recommended_some_beauty: ValidateTask = {
    "state_key": {
        "users": {"collection": "users", "filter": {}},
        "posts": {"collection": "posts", "filter": {}},
    },
    "validate": _validate_friend_recommended_some_beauty,
}


# =============================================================================
# Task 3: This eye strain is getting ridiculous working late nights. Switch the app to dar...
# =============================================================================

def _validate_this_eye_strain_getting(
    final_state_backend: Backend, final_state_frontend: Dict[str, Any]
) -> Tuple[float, str]:
    """Validate This eye strain is getting ridiculous working late nights. S...
    """
    theme_mode = final_state_frontend.get("themeMode")
    if theme_mode != "dark":
        return 0.0, f"Expected themeMode='dark', got '{theme_mode}'"
    page = final_state_frontend.get("page")
    if page != "notifications":
        return 0.0, f"Expected page='notifications', got '{page}'"

    return 1.0, "Task completed successfully"


_validate_this_eye_strain_getting: ValidateTask = {
    "state_key": {
    },
    "validate": _validate_this_eye_strain_getting,
}


# =============================================================================
# Task 4: I want to learn some simple recipes for meal prep—nothing too fancy, just practi...
# =============================================================================

def _validate_want_learn_some_simple(
    final_state_backend: Backend, final_state_frontend: Dict[str, Any]
) -> Tuple[float, str]:
    """Validate I want to learn some simple recipes for meal prep—nothing to...
    
    Initial State Assumptions:
    - currentUser.following is empty [] before task starts
    - currentUser.bookmarks is empty [] before task starts
    - currentUser.albums is empty [] before task starts
    """
    current_user_id = final_state_frontend.get("currentUserId", "0")
    if not current_user_id:
        return 0.0, "currentUserId missing in frontend state"
    
    try:
        current_user = _get_current_user(final_state_backend)
    except ValueError as e:
        return 0.0, str(e)
    
    # Check following count
    following = current_user.get("following", [])
    if not isinstance(following, list):
        return 0.0, "following is not a list"
    if len(following) < 1:
        return 0.0, f"Expected at least 1 followed user(s), got {len(following)}"
    
    # Check if followed users are food-related
    food_following_count = 0
    for user_id in following:
        try:
            user = _get_user(final_state_backend, user_id)
            if _check_user_category_relevance(user, "food"):
                food_following_count += 1
        except ValueError:
            continue
    
    if food_following_count < 1:
        return 0.0, f"Expected at least 1 food-related followed user(s), got {food_following_count}"

    # Check bookmarks count
    bookmarks = current_user.get("bookmarks", [])
    if not isinstance(bookmarks, list):
        return 0.0, "bookmarks is not a list"
    if len(bookmarks) < 3:
        return 0.0, f"Expected at least 3 bookmarked post(s), got {len(bookmarks)}"
    
    # Check if bookmarked posts are food-related
    food_bookmarks_count = 0
    for post_id in bookmarks:
        try:
            post = _get_post(final_state_backend, post_id)
            if _check_topic_relevance(post, "food"):
                food_bookmarks_count += 1
        except ValueError:
            continue
    
    if food_bookmarks_count < 3:
        return 0.0, f"Expected at least 3 food-related bookmarked posts, got {food_bookmarks_count}"

    # Check for album with at least 3 posts
    albums = current_user.get("albums", [])
    if not isinstance(albums, list):
        return 0.0, "albums is not a list"
    
    album_found = None
    for album in albums:
        post_ids = album.get("postIds", [])
        if isinstance(post_ids, list) and len(post_ids) >= 3:
            album_found = album
            break
    
    if not album_found:
        return 0.0, f"No album found with at least 3 posts"

    return 1.0, "Task completed successfully"


_validate_want_learn_some_simple: ValidateTask = {
    "state_key": {
        "users": {"collection": "users", "filter": {}},
        "posts": {"collection": "posts", "filter": {}},
    },
    "validate": _validate_want_learn_some_simple,
}


# =============================================================================
# Task 5: Saw an amazing travel photo earlier and want to leave a nice comment telling the...
# =============================================================================

def _validate_saw_amazing_travel_photo(
    final_state_backend: Backend, final_state_frontend: Dict[str, Any]
) -> Tuple[float, str]:
    """Validate Saw an amazing travel photo earlier and want to leave a nice...
    
    Initial State Assumptions:
    - No comments from currentUser exist before task starts
    """
    current_user_id = final_state_frontend.get("currentUserId", "0")
    if not current_user_id:
        return 0.0, "currentUserId missing in frontend state"
    
    try:
        current_user = _get_current_user(final_state_backend)
    except ValueError as e:
        return 0.0, str(e)
    
    # Check for comment on travel-related post
    # Query comments collection for comments by current user
    user_comments = final_state_backend.query({"collection": "comments", "filter": {"authorId": current_user_id}})
    travel_comment_found = False
    
    for comment in user_comments:
        post_id = comment.get("postId")
        if not post_id:
            continue
        
        try:
            post = _get_post(final_state_backend, post_id)
            if _check_topic_relevance(post, "travel"):
                travel_comment_found = True
                break
        except ValueError:
            continue
    
    if not travel_comment_found:
        return 0.0, "No comment found on travel-related post"

    return 1.0, "Task completed successfully"


_validate_saw_amazing_travel_photo: ValidateTask = {
    "state_key": {
        "users": {"collection": "users", "filter": {}},
        "posts": {"collection": "posts", "filter": {}},
        "comments": {"collection": "comments", "filter": {}},
    },
    "validate": _validate_saw_amazing_travel_photo,
}


# =============================================================================
# Task 6: I'm redecorating my small bedroom and looking for space-saving ideas that actual...
# =============================================================================

# def _validate_redecorating_small_bedroom_and(
#     final_state_backend: Backend, final_state_frontend: Dict[str, Any]
# ) -> Tuple[float, str]:
#     """Validate I'm redecorating my small bedroom and looking for space-savi...
    
#     Initial State Assumptions:
#     - currentUser.following is empty [] before task starts
#     - currentUser.bookmarks is empty [] before task starts
#     - currentUser.albums is empty [] before task starts
#     """
#     current_user_id = final_state_frontend.get("currentUserId", "0")
#     if not current_user_id:
#         return 0.0, "currentUserId missing in frontend state"
    
#     try:
#         current_user = _get_current_user(final_state_backend)
#     except ValueError as e:
#         return 0.0, str(e)
    
#     # Check following count
#     following = current_user.get("following", [])
#     if not isinstance(following, list):
#         return 0.0, "following is not a list"
#     if len(following) < 2:
#         return 0.0, f"Expected at least 2 followed user(s), got {len(following)}"
    
#     # Check if followed users are home-related
#     home_following_count = 0
#     for user_id in following:
#         try:
#             user = _get_user(final_state_backend, user_id)
#             if _check_user_category_relevance(user, "home"):
#                 home_following_count += 1
#         except ValueError:
#             continue
    
#     if home_following_count < 2:
#         return 0.0, f"Expected at least 2 home-related followed user(s), got {home_following_count}"

#     # Check bookmarks count
#     bookmarks = current_user.get("bookmarks", [])
#     if not isinstance(bookmarks, list):
#         return 0.0, "bookmarks is not a list"
#     if len(bookmarks) < 3:
#         return 0.0, f"Expected at least 3 bookmarked post(s), got {len(bookmarks)}"
    
#     # Check if bookmarked posts are home-related
#     home_bookmarks_count = 0
#     for post_id in bookmarks:
#         try:
#             post = _get_post(final_state_backend, post_id)
#             if _check_topic_relevance(post, "home"):
#                 home_bookmarks_count += 1
#         except ValueError:
#             continue
    
#     if home_bookmarks_count < 3:
#         return 0.0, f"Expected at least 3 home-related bookmarked posts, got {home_bookmarks_count}"

#     # Check for album with at least 3 posts
#     albums = current_user.get("albums", [])
#     if not isinstance(albums, list):
#         return 0.0, "albums is not a list"
    
#     album_found = None
#     for album in albums:
#         post_ids = album.get("postIds", [])
#         if isinstance(post_ids, list) and len(post_ids) >= 3:
#             album_found = album
#             break
    
#     if not album_found:
#         return 0.0, f"No album found with at least 3 posts"

#     return 1.0, "Task completed successfully"


# _validate_redecorating_small_bedroom_and: ValidateTask = {
#     "state_key": {
#         "users": {"collection": "users", "filter": {}},
#         "posts": {"collection": "posts", "filter": {}},
#     },
#     "validate": _validate_redecorating_small_bedroom_and,
# }


# =============================================================================
# Task 7: Need to find some quick skincare routine ideas for someone who's always rushing ...
# =============================================================================

def _validate_need_find_some_quick(
    final_state_backend: Backend, final_state_frontend: Dict[str, Any]
) -> Tuple[float, str]:
    """Validate Need to find some quick skincare routine ideas for someone w...
    
    Initial State Assumptions:
    - currentUser.searchHistory is empty [] before task starts
    - currentUser.bookmarks is empty [] before task starts
    """
    current_user_id = final_state_frontend.get("currentUserId", "0")
    if not current_user_id:
        return 0.0, "currentUserId missing in frontend state"
    
    try:
        current_user = _get_current_user(final_state_backend)
    except ValueError as e:
        return 0.0, str(e)
    
    # Check searchHistory for skincare-related search
    search_history = final_state_backend.query({"collection": "searchHistory", "filter": {"userId": current_user_id}})
    if not isinstance(search_history, list):
        search_history = []
    
    search_queries = [entry.get("query", "").lower() for entry in search_history if isinstance(entry, dict)]
    skincare_keywords = ["skincare", "护肤", "美容", "routine"]
    has_skincare_search = any(
        any(keyword in query for keyword in skincare_keywords)
        for query in search_queries
    )
    if not has_skincare_search:
        return 0.0, f"searchHistory should contain skincare-related search terms, got: {search_queries}"

    # Check bookmarks count
    bookmarks = current_user.get("bookmarks", [])
    if not isinstance(bookmarks, list):
        return 0.0, "bookmarks is not a list"
    if len(bookmarks) < 1:
        return 0.0, f"Expected at least 1 bookmarked post(s), got {len(bookmarks)}"
    
    # Check if bookmarked posts are beauty-related
    beauty_bookmarks_count = 0
    for post_id in bookmarks:
        try:
            post = _get_post(final_state_backend, post_id)
            if _check_topic_relevance(post, "beauty"):
                beauty_bookmarks_count += 1
        except ValueError:
            continue
    
    if beauty_bookmarks_count < 1:
        return 0.0, f"Expected at least 1 beauty-related bookmarked post(s), got {beauty_bookmarks_count}"

    return 1.0, "Task completed successfully"


_validate_need_find_some_quick: ValidateTask = {
    "state_key": {
        "users": {"collection": "users", "filter": {}},
        "posts": {"collection": "posts", "filter": {}},
        "searchHistory": {"collection": "searchHistory", "filter": {}},
    },
    "validate": _validate_need_find_some_quick,
}


# =============================================================================
# Task 8: My cat has been acting weird lately and I want to see if other pet owners have d...
# =============================================================================

def _validate_cat_has_been_acting(
    final_state_backend: Backend, final_state_frontend: Dict[str, Any]
) -> Tuple[float, str]:
    """Validate My cat has been acting weird lately and I want to see if oth...
    
    Initial State Assumptions:
    - currentUser.following is empty [] before task starts
    - currentUser.bookmarks is empty [] before task starts
    - currentUser.liked is empty [] before task starts
    """
    current_user_id = final_state_frontend.get("currentUserId", "0")
    if not current_user_id:
        return 0.0, "currentUserId missing in frontend state"
    
    try:
        current_user = _get_current_user(final_state_backend)
    except ValueError as e:
        return 0.0, str(e)
    
    # Check following count
    following = current_user.get("following", [])
    if not isinstance(following, list):
        return 0.0, "following is not a list"
    if len(following) < 1:
        return 0.0, f"Expected at least 1 followed user(s), got {len(following)}"
    
    # Check if followed users are pets-related
    pets_following_count = 0
    for user_id in following:
        try:
            user = _get_user(final_state_backend, user_id)
            if _check_user_category_relevance(user, "pets"):
                pets_following_count += 1
        except ValueError:
            continue
    
    if pets_following_count < 1:
        return 0.0, f"Expected at least 1 pets-related followed user(s), got {pets_following_count}"

    # Check bookmarks or liked posts (at least 2)
    bookmarks = current_user.get("bookmarks", [])
    liked = current_user.get("liked", [])
    
    pets_content_count = 0
    for post_id in list(bookmarks) + list(liked):
        try:
            post = _get_post(final_state_backend, post_id)
            if _check_topic_relevance(post, "pets"):
                pets_content_count += 1
        except ValueError:
            continue
    
    if pets_content_count < 2:
        return 0.0, f"Expected at least 2 pets-related bookmarked or liked posts, got {pets_content_count}"

    return 1.0, "Task completed successfully"


_validate_cat_has_been_acting: ValidateTask = {
    "state_key": {
        "users": {"collection": "users", "filter": {}},
        "posts": {"collection": "posts", "filter": {}},
    },
    "validate": _validate_cat_has_been_acting,
}


# =============================================================================
# Task 9: Planning a weekend trip to 杭州 and want authentic local food recommendations, not...
# =============================================================================

def _validate_planning_weekend_trip_and(
    final_state_backend: Backend, final_state_frontend: Dict[str, Any]
) -> Tuple[float, str]:
    """Validate Planning a weekend trip to 杭州 and want authentic local food ...
    
    Initial State Assumptions:
    - currentUser.searchHistory is empty [] before task starts
    - currentUser.bookmarks is empty [] before task starts
    """
    current_user_id = final_state_frontend.get("currentUserId", "0")
    if not current_user_id:
        return 0.0, "currentUserId missing in frontend state"
    
    try:
        current_user = _get_current_user(final_state_backend)
    except ValueError as e:
        return 0.0, str(e)
    
    # Check searchHistory for 杭州-related search
    search_history = final_state_backend.query({"collection": "searchHistory", "filter": {"userId": current_user_id}})
    if not isinstance(search_history, list):
        search_history = []
    
    search_queries = [entry.get("query", "") for entry in search_history if isinstance(entry, dict)]
    has_hangzhou_search = any("杭州" in query for query in search_queries)
    if not has_hangzhou_search:
        return 0.0, f"searchHistory should contain '杭州' in search query, got: {search_queries}"
    
    # Check bookmarks count
    bookmarks = current_user.get("bookmarks", [])
    if not isinstance(bookmarks, list):
        return 0.0, "bookmarks is not a list"
    if len(bookmarks) < 3:
        return 0.0, f"Expected at least 3 bookmarked post(s), got {len(bookmarks)}"
    
    # Check if bookmarked posts are travel-related
    travel_bookmarks_count = 0
    for post_id in bookmarks:
        try:
            post = _get_post(final_state_backend, post_id)
            if _check_topic_relevance(post, "travel"):
                travel_bookmarks_count += 1
        except ValueError:
            continue
    
    if travel_bookmarks_count < 3:
        return 0.0, f"Expected at least 3 travel-related bookmarked posts, got {travel_bookmarks_count}"

    return 1.0, "Task completed successfully"


_validate_planning_weekend_trip_and: ValidateTask = {
    "state_key": {
        "users": {"collection": "users", "filter": {}},
        "posts": {"collection": "posts", "filter": {}},
        "searchHistory": {"collection": "searchHistory", "filter": {}},
    },
    "validate": _validate_planning_weekend_trip_and,
}


# =============================================================================
# Task 10: Someone posted amazing nail art that I want to try myself. Find a nail tutorial ...
# =============================================================================

def _validate_someone_posted_amazing_nail(
    final_state_backend: Backend, final_state_frontend: Dict[str, Any]
) -> Tuple[float, str]:
    """Validate Someone posted amazing nail art that I want to try myself. F...
    
    Initial State Assumptions:
    - No comments from currentUser exist before task starts
    """
    current_user_id = final_state_frontend.get("currentUserId", "0")
    if not current_user_id:
        return 0.0, "currentUserId missing in frontend state"
    
    try:
        current_user = _get_current_user(final_state_backend)
    except ValueError as e:
        return 0.0, str(e)
    
    # Check for comment on beauty-related post
    # Query comments collection for comments by current user
    user_comments = final_state_backend.query({"collection": "comments", "filter": {"authorId": current_user_id}})
    beauty_comment_found = False
    
    for comment in user_comments:
        post_id = comment.get("postId")
        if not post_id:
            continue
        
        try:
            post = _get_post(final_state_backend, post_id)
            if _check_topic_relevance(post, "beauty"):
                beauty_comment_found = True
                break
        except ValueError:
            continue
    
    if not beauty_comment_found:
        return 0.0, "No comment found on beauty-related post"

    return 1.0, "Task completed successfully"


_validate_someone_posted_amazing_nail: ValidateTask = {
    "state_key": {
        "users": {"collection": "users", "filter": {}},
        "posts": {"collection": "posts", "filter": {}},
        "comments": {"collection": "comments", "filter": {}},
    },
    "validate": _validate_someone_posted_amazing_nail,
}


# =============================================================================
# Task 11: I've been getting back into drawing and need some inspiration from other artists...
# =============================================================================

def _validate_been_getting_back_into(
    final_state_backend: Backend, final_state_frontend: Dict[str, Any]
) -> Tuple[float, str]:
    """Validate I've been getting back into drawing and need some inspiratio...
    
    Initial State Assumptions:
    - currentUser.following is empty [] before task starts
    - currentUser.bookmarks is empty [] before task starts
    - currentUser.liked is empty [] before task starts
    """
    current_user_id = final_state_frontend.get("currentUserId", "0")
    if not current_user_id:
        return 0.0, "currentUserId missing in frontend state"
    
    try:
        current_user = _get_current_user(final_state_backend)
    except ValueError as e:
        return 0.0, str(e)
    
    # Check following count
    following = current_user.get("following", [])
    if not isinstance(following, list):
        return 0.0, "following is not a list"
    if len(following) < 2:
        return 0.0, f"Expected at least 2 followed user(s), got {len(following)}"
    
    # Check if followed users are art-related
    art_following_count = 0
    for user_id in following:
        try:
            user = _get_user(final_state_backend, user_id)
            if _check_user_category_relevance(user, "art"):
                art_following_count += 1
        except ValueError:
            continue
    
    if art_following_count < 2:
        return 0.0, f"Expected at least 2 art-related followed user(s), got {art_following_count}"

    # Check bookmarks or liked posts (at least 2)
    bookmarks = current_user.get("bookmarks", [])
    liked = current_user.get("liked", [])
    
    art_content_count = 0
    for post_id in list(bookmarks) + list(liked):
        try:
            post = _get_post(final_state_backend, post_id)
            if _check_topic_relevance(post, "art"):
                art_content_count += 1
        except ValueError:
            continue
    
    if art_content_count < 2:
        return 0.0, f"Expected at least 2 art-related bookmarked or liked posts, got {art_content_count}"

    return 1.0, "Task completed successfully"


_validate_been_getting_back_into: ValidateTask = {
    "state_key": {
        "users": {"collection": "users", "filter": {}},
        "posts": {"collection": "posts", "filter": {}},
    },
    "validate": _validate_been_getting_back_into,
}


# =============================================================================
# Task 12: Looking for budget-friendly fashion inspiration since I'm trying to save money b...
# =============================================================================

def _validate_looking_for_budget_friendly(
    final_state_backend: Backend, final_state_frontend: Dict[str, Any]
) -> Tuple[float, str]:
    """Validate Looking for budget-friendly fashion inspiration since I'm tr...
    
    Initial State Assumptions:
    - currentUser.searchHistory is empty [] before task starts
    - currentUser.following is empty [] before task starts
    - currentUser.bookmarks is empty [] before task starts
    """
    current_user_id = final_state_frontend.get("currentUserId", "0")
    if not current_user_id:
        return 0.0, "currentUserId missing in frontend state"
    
    try:
        current_user = _get_current_user(final_state_backend)
    except ValueError as e:
        return 0.0, str(e)
    
    # Check searchHistory for fashion-related search (Chinese terms)
    search_history = final_state_backend.query({"collection": "searchHistory", "filter": {"userId": current_user_id}})
    if not isinstance(search_history, list):
        search_history = []
    
    search_queries = [entry.get("query", "") for entry in search_history if isinstance(entry, dict)]
    fashion_keywords = ["时尚", "穿搭", "搭配", "服装", "服饰", "穿衣", "ootd"]
    has_fashion_search = any(
        any(keyword in query for keyword in fashion_keywords)
        for query in search_queries
    )
    if not has_fashion_search:
        return 0.0, f"searchHistory should contain fashion-related search terms (时尚, 穿搭, etc.), got: {search_queries}"

    # Check following count
    following = current_user.get("following", [])
    if not isinstance(following, list):
        return 0.0, "following is not a list"
    if len(following) < 1:
        return 0.0, f"Expected at least 1 followed user(s), got {len(following)}"
    
    # Check if followed users are fashion-related
    fashion_following_count = 0
    for user_id in following:
        try:
            user = _get_user(final_state_backend, user_id)
            if _check_user_category_relevance(user, "fashion"):
                fashion_following_count += 1
        except ValueError:
            continue
    
    if fashion_following_count < 1:
        return 0.0, f"Expected at least 1 fashion-related followed user(s), got {fashion_following_count}"

    # Check bookmarks count
    bookmarks = current_user.get("bookmarks", [])
    if not isinstance(bookmarks, list):
        return 0.0, "bookmarks is not a list"
    if len(bookmarks) < 2:
        return 0.0, f"Expected at least 2 bookmarked post(s), got {len(bookmarks)}"
    
    # Check if bookmarked posts are fashion-related
    fashion_bookmarks_count = 0
    for post_id in bookmarks:
        try:
            post = _get_post(final_state_backend, post_id)
            if _check_topic_relevance(post, "fashion"):
                fashion_bookmarks_count += 1
        except ValueError:
            continue
    
    if fashion_bookmarks_count < 2:
        return 0.0, f"Expected at least 2 fashion-related bookmarked posts, got {fashion_bookmarks_count}"

    return 1.0, "Task completed successfully"


_validate_looking_for_budget_friendly: ValidateTask = {
    "state_key": {
        "users": {"collection": "users", "filter": {}},
        "posts": {"collection": "posts", "filter": {}},
        "searchHistory": {"collection": "searchHistory", "filter": {}},
    },
    "validate": _validate_looking_for_budget_friendly,
}


# =============================================================================
# Task 13: This bright screen is hurting my eyes during my late-night scrolling sessions. C...
# =============================================================================

def _validate_this_bright_screen_hurting(
    final_state_backend: Backend, final_state_frontend: Dict[str, Any]
) -> Tuple[float, str]:
    """Validate This bright screen is hurting my eyes during my late-night s...
    """
    theme_mode = final_state_frontend.get("themeMode")
    if theme_mode != "dark":
        return 0.0, f"Expected themeMode='dark', got '{theme_mode}'"

    return 1.0, "Task completed successfully"


_validate_this_bright_screen_hurting: ValidateTask = {
    "state_key": {
    },
    "validate": _validate_this_bright_screen_hurting,
}


# =============================================================================
# Task 14: My workout motivation has been lacking lately. Find some inspiring fitness trans...
# =============================================================================

def _validate_workout_motivation_has_been(
    final_state_backend: Backend, final_state_frontend: Dict[str, Any]
) -> Tuple[float, str]:
    """Validate My workout motivation has been lacking lately. Find some ins...
    
    Initial State Assumptions:
    - No comments from currentUser exist before task starts
    """
    current_user_id = final_state_frontend.get("currentUserId", "0")
    if not current_user_id:
        return 0.0, "currentUserId missing in frontend state"
    
    try:
        current_user = _get_current_user(final_state_backend)
    except ValueError as e:
        return 0.0, str(e)
    
    # Check for 2 comments on fitness-related posts
    # Query comments collection for comments by current user
    user_comments = final_state_backend.query({"collection": "comments", "filter": {"authorId": current_user_id}})
    comment_count = 0
    
    for comment in user_comments:
        post_id = comment.get("postId")
        if not post_id:
            continue
        
        try:
            post = _get_post(final_state_backend, post_id)
            if _check_topic_relevance(post, "fitness"):
                comment_count += 1
        except ValueError:
            continue
    
    if comment_count < 2:
        return 0.0, f"Expected at least 2 comments on fitness-related posts, got {comment_count}"

    return 1.0, "Task completed successfully"


_validate_workout_motivation_has_been: ValidateTask = {
    "state_key": {
        "users": {"collection": "users", "filter": {}},
        "posts": {"collection": "posts", "filter": {}},
        "comments": {"collection": "comments", "filter": {}},
    },
    "validate": _validate_workout_motivation_has_been,
}


# =============================================================================
# Task 15: Need to organize my tiny kitchen better and looking for clever storage hacks tha...
# =============================================================================

def _validate_need_organize_tiny_kitchen(
    final_state_backend: Backend, final_state_frontend: Dict[str, Any]
) -> Tuple[float, str]:
    """Validate Need to organize my tiny kitchen better and looking for clev...
    
    Initial State Assumptions:
    - currentUser.following is empty [] before task starts
    - currentUser.bookmarks is empty [] before task starts
    - currentUser.albums is empty [] before task starts
    """
    current_user_id = final_state_frontend.get("currentUserId", "0")
    if not current_user_id:
        return 0.0, "currentUserId missing in frontend state"
    
    try:
        current_user = _get_current_user(final_state_backend)
    except ValueError as e:
        return 0.0, str(e)
    
    # Check following count
    following = current_user.get("following", [])
    if not isinstance(following, list):
        return 0.0, "following is not a list"
    if len(following) < 1:
        return 0.0, f"Expected at least 1 followed user(s), got {len(following)}"
    
    # Check if followed users are home-related
    home_following_count = 0
    for user_id in following:
        try:
            user = _get_user(final_state_backend, user_id)
            if _check_user_category_relevance(user, "home"):
                home_following_count += 1
        except ValueError:
            continue
    
    if home_following_count < 1:
        return 0.0, f"Expected at least 1 home-related followed user(s), got {home_following_count}"

    # Check bookmarks count
    bookmarks = current_user.get("bookmarks", [])
    if not isinstance(bookmarks, list):
        return 0.0, "bookmarks is not a list"
    if len(bookmarks) < 3:
        return 0.0, f"Expected at least 3 bookmarked post(s), got {len(bookmarks)}"
    
    # Check if bookmarked posts are home-related
    home_bookmarks_count = 0
    for post_id in bookmarks:
        try:
            post = _get_post(final_state_backend, post_id)
            if _check_topic_relevance(post, "home"):
                home_bookmarks_count += 1
        except ValueError:
            continue
    
    if home_bookmarks_count < 3:
        return 0.0, f"Expected at least 3 home-related bookmarked posts, got {home_bookmarks_count}"

    # Check for album with at least 3 posts
    albums = current_user.get("albums", [])
    if not isinstance(albums, list):
        return 0.0, "albums is not a list"
    
    album_found = None
    for album in albums:
        post_ids = album.get("postIds", [])
        if isinstance(post_ids, list) and len(post_ids) >= 3:
            album_found = album
            break
    
    if not album_found:
        return 0.0, f"No album found with at least 3 posts"

    return 1.0, "Task completed successfully"


_validate_need_organize_tiny_kitchen: ValidateTask = {
    "state_key": {
        "users": {"collection": "users", "filter": {}},
        "posts": {"collection": "posts", "filter": {}},
    },
    "validate": _validate_need_organize_tiny_kitchen,
}


# =============================================================================
# Task 16: I want to try some new hairstyles but my hair is pretty basic and I don't want a...
# =============================================================================

def _validate_want_try_some_new(
    final_state_backend: Backend, final_state_frontend: Dict[str, Any]
) -> Tuple[float, str]:
    """Validate I want to try some new hairstyles but my hair is pretty basi...
    
    Initial State Assumptions:
    - currentUser.searchHistory is empty [] before task starts
    - currentUser.bookmarks is empty [] before task starts
    - currentUser.albums is empty [] before task starts
    """
    current_user_id = final_state_frontend.get("currentUserId", "0")
    if not current_user_id:
        return 0.0, "currentUserId missing in frontend state"
    
    try:
        current_user = _get_current_user(final_state_backend)
    except ValueError as e:
        return 0.0, str(e)
    
    # Check searchHistory for hair/beauty-related search (Chinese terms)
    search_history = final_state_backend.query({"collection": "searchHistory", "filter": {"userId": current_user_id}})
    if not isinstance(search_history, list):
        search_history = []
    
    search_queries = [entry.get("query", "") for entry in search_history if isinstance(entry, dict)]
    hair_beauty_keywords = ["发型", "美发", "教程", "头发", "编发", "造型", "美容", "化妆", "美妆", "护肤"]
    has_hair_beauty_search = any(
        any(keyword in query for keyword in hair_beauty_keywords)
        for query in search_queries
    )
    if not has_hair_beauty_search:
        return 0.0, f"searchHistory should contain hair/beauty tutorial-related search terms (发型, 教程, etc.), got: {search_queries}"
    
    # Check bookmarks OR album with beauty-related posts (at least 3)
    bookmarks = current_user.get("bookmarks", [])
    if not isinstance(bookmarks, list):
        return 0.0, "bookmarks is not a list"
    
    # Check if bookmarked posts are beauty-related
    beauty_bookmarks_count = 0
    for post_id in bookmarks:
        try:
            post = _get_post(final_state_backend, post_id)
            if _check_topic_relevance(post, "beauty"):
                beauty_bookmarks_count += 1
        except ValueError:
            continue
    
    # Check for album with at least 3 beauty-related posts
    albums = current_user.get("albums", [])
    if not isinstance(albums, list):
        albums = []
    
    beauty_album_posts_count = 0
    for album in albums:
        post_ids = album.get("postIds", [])
        if isinstance(post_ids, list):
            for post_id in post_ids:
                try:
                    post = _get_post(final_state_backend, post_id)
                    if _check_topic_relevance(post, "beauty"):
                        beauty_album_posts_count += 1
                except ValueError:
                    continue
    
    # Pass if either condition is met: bookmarked posts OR album posts
    if beauty_bookmarks_count < 3 and beauty_album_posts_count < 3:
        return 0.0, f"Expected at least 3 beauty-related posts either bookmarked (got {beauty_bookmarks_count}) or in a collection (got {beauty_album_posts_count})"

    return 1.0, "Task completed successfully"


_validate_want_try_some_new: ValidateTask = {
    "state_key": {
        "users": {"collection": "users", "filter": {}},
        "posts": {"collection": "posts", "filter": {}},
        "searchHistory": {"collection": "searchHistory", "filter": {}},
    },
    "validate": _validate_want_try_some_new,
}


# =============================================================================
# Task 17: Thinking about getting a dog and want to see what daily life with pets actually ...
# =============================================================================

def _validate_thinking_about_getting_dog(
    final_state_backend: Backend, final_state_frontend: Dict[str, Any]
) -> Tuple[float, str]:
    """Validate Thinking about getting a dog and want to see what daily life...
    
    Initial State Assumptions:
    - currentUser.following is empty [] before task starts
    """
    current_user_id = final_state_frontend.get("currentUserId", "0")
    if not current_user_id:
        return 0.0, "currentUserId missing in frontend state"
    
    try:
        current_user = _get_current_user(final_state_backend)
    except ValueError as e:
        return 0.0, str(e)
    
    # Check following count
    following = current_user.get("following", [])
    if not isinstance(following, list):
        return 0.0, "following is not a list"
    if len(following) < 2:
        return 0.0, f"Expected at least 2 followed user(s), got {len(following)}"
    
    # Check if followed users are pets-related
    pets_following_count = 0
    for user_id in following:
        try:
            user = _get_user(final_state_backend, user_id)
            if _check_user_category_relevance(user, "pets"):
                pets_following_count += 1
        except ValueError:
            continue
    
    if pets_following_count < 2:
        return 0.0, f"Expected at least 2 pets-related followed user(s), got {pets_following_count}"

    return 1.0, "Task completed successfully"


_validate_thinking_about_getting_dog: ValidateTask = {
    "state_key": {
        "users": {"collection": "users", "filter": {}},
        "posts": {"collection": "posts", "filter": {}},
    },
    "validate": _validate_thinking_about_getting_dog,
}


# =============================================================================
# Task 18: Someone shared a really creative DIY project that caught my attention. Find a cr...
# =============================================================================

def _validate_someone_shared_really_creative(
    final_state_backend: Backend, final_state_frontend: Dict[str, Any]
) -> Tuple[float, str]:
    """Validate Someone shared a really creative DIY project that caught my ...
    
    Initial State Assumptions:
    - No comments from currentUser exist before task starts
    """
    current_user_id = final_state_frontend.get("currentUserId", "0")
    if not current_user_id:
        return 0.0, "currentUserId missing in frontend state"
    
    try:
        current_user = _get_current_user(final_state_backend)
    except ValueError as e:
        return 0.0, str(e)
    
    # Check for comment on art-related post
    # Query comments collection for comments by current user
    user_comments = final_state_backend.query({"collection": "comments", "filter": {"authorId": current_user_id}})
    art_comment_found = False
    
    for comment in user_comments:
        post_id = comment.get("postId")
        if not post_id:
            continue
        
        try:
            post = _get_post(final_state_backend, post_id)
            if _check_topic_relevance(post, "art"):
                art_comment_found = True
                break
        except ValueError:
            continue
    
    if not art_comment_found:
        return 0.0, "No comment found on art-related post"

    return 1.0, "Task completed successfully"


_validate_someone_shared_really_creative: ValidateTask = {
    "state_key": {
        "users": {"collection": "users", "filter": {}},
        "posts": {"collection": "posts", "filter": {}},
        "comments": {"collection": "comments", "filter": {}},
    },
    "validate": _validate_someone_shared_really_creative,
}


# =============================================================================
# Task 19: I'm trying to eat healthier but don't want to give up flavor. Search for healthy...
# =============================================================================

def _validate_trying_eat_healthier_but(
    final_state_backend: Backend, final_state_frontend: Dict[str, Any]
) -> Tuple[float, str]:
    """Validate I'm trying to eat healthier but don't want to give up flavor...
    
    Initial State Assumptions:
    - currentUser.searchHistory is empty [] before task starts
    - currentUser.bookmarks is empty [] before task starts
    - currentUser.albums is empty [] before task starts
    """
    current_user_id = final_state_frontend.get("currentUserId", "0")
    if not current_user_id:
        return 0.0, "currentUserId missing in frontend state"
    
    try:
        current_user = _get_current_user(final_state_backend)
    except ValueError as e:
        return 0.0, str(e)
    
    # Check searchHistory for healthy/recipe-related search (Chinese terms)
    search_history = final_state_backend.query({"collection": "searchHistory", "filter": {"userId": current_user_id}})
    if not isinstance(search_history, list):
        search_history = []
    
    search_queries = [entry.get("query", "") for entry in search_history if isinstance(entry, dict)]
    healthy_food_keywords = ["健康", "食谱", "健康食谱", "减脂餐", "低卡", "营养", "轻食", "健康饮食", "健康美食", "健康料理"]
    has_healthy_food_search = any(
        any(keyword in query for keyword in healthy_food_keywords)
        for query in search_queries
    )
    if not has_healthy_food_search:
        return 0.0, f"searchHistory should contain healthy/recipe-related search terms (健康, 食谱, etc.), got: {search_queries}"

    # Check bookmarks OR album with food-related posts (at least 3)
    bookmarks = current_user.get("bookmarks", [])
    if not isinstance(bookmarks, list):
        return 0.0, "bookmarks is not a list"
    
    # Check if bookmarked posts are food-related
    food_bookmarks_count = 0
    for post_id in bookmarks:
        try:
            post = _get_post(final_state_backend, post_id)
            if _check_topic_relevance(post, "food"):
                food_bookmarks_count += 1
        except ValueError:
            continue
    
    # Check for album with at least 3 food-related posts
    albums = current_user.get("albums", [])
    if not isinstance(albums, list):
        albums = []
    
    food_album_posts_count = 0
    for album in albums:
        post_ids = album.get("postIds", [])
        if isinstance(post_ids, list):
            for post_id in post_ids:
                try:
                    post = _get_post(final_state_backend, post_id)
                    if _check_topic_relevance(post, "food"):
                        food_album_posts_count += 1
                except ValueError:
                    continue
    
    # Pass if either condition is met: bookmarked posts OR album posts
    if food_bookmarks_count < 3 and food_album_posts_count < 3:
        return 0.0, f"Expected at least 3 food-related posts either bookmarked (got {food_bookmarks_count}) or in a collection (got {food_album_posts_count})"

    return 1.0, "Task completed successfully"


_validate_trying_eat_healthier_but: ValidateTask = {
    "state_key": {
        "users": {"collection": "users", "filter": {}},
        "posts": {"collection": "posts", "filter": {}},
        "searchHistory": {"collection": "searchHistory", "filter": {}},
    },
    "validate": _validate_trying_eat_healthier_but,
}


# =============================================================================
# Task 20: Want to support some smaller creators by engaging with their content. Find posts...
# =============================================================================

def _validate_want_support_some_smaller(
    final_state_backend: Backend, final_state_frontend: Dict[str, Any]
) -> Tuple[float, str]:
    """Validate Want to support some smaller creators by engaging with their...
    
    Initial State Assumptions:
    - No comments from currentUser exist before task starts
    """
    current_user_id = final_state_frontend.get("currentUserId", "0")
    if not current_user_id:
        return 0.0, "currentUserId missing in frontend state"
    
    try:
        current_user = _get_current_user(final_state_backend)
    except ValueError as e:
        return 0.0, str(e)
    
    # Check for 3 comments on posts with less than 1000 likes
    # Query comments collection for comments by current user
    user_comments = final_state_backend.query({"collection": "comments", "filter": {"authorId": current_user_id}})
    comment_count = 0
    
    for comment in user_comments:
        post_id = comment.get("postId")
        if not post_id:
            continue
        
        try:
            post = _get_post(final_state_backend, post_id)
            # Check that post has less than 1000 likes
            post_likes = post.get("likes", 0)
            if not isinstance(post_likes, (int, float)):
                continue
            if post_likes >= 1000:
                continue
            # Post has less than 1000 likes, count this comment
            comment_count += 1
        except ValueError:
            continue
    
    if comment_count < 3:
        return 0.0, f"Expected at least 3 comments on posts with less than 1000 likes, got {comment_count}"

    return 1.0, "Task completed successfully"


_validate_want_support_some_smaller: ValidateTask = {
    "state_key": {
        "users": {"collection": "users", "filter": {}},
        "posts": {"collection": "posts", "filter": {}},
        "comments": {"collection": "comments", "filter": {}},
    },
    "validate": _validate_want_support_some_smaller,
}

### Checked up to here

# =============================================================================
# Task 21: Planning to redecorate my living room with a cozy, minimalist vibe. Collect some...
# =============================================================================

def _validate_planning_redecorate_living_room(
    final_state_backend: Backend, final_state_frontend: Dict[str, Any]
) -> Tuple[float, str]:
    """Validate Planning to redecorate my living room with a cozy, minimalis...
    
    Initial State Assumptions:
    - currentUser.following is empty [] before task starts
    - currentUser.bookmarks is empty [] before task starts
    - currentUser.albums is empty [] before task starts
    """
    current_user_id = final_state_frontend.get("currentUserId", "0")
    if not current_user_id:
        return 0.0, "currentUserId missing in frontend state"
    
    try:
        current_user = _get_current_user(final_state_backend)
    except ValueError as e:
        return 0.0, str(e)
    
    # Check following count
    following = current_user.get("following", [])
    if not isinstance(following, list):
        return 0.0, "following is not a list"
    if len(following) < 2:
        return 0.0, f"Expected at least 2 followed user(s), got {len(following)}"
    
    # Check if followed users are home-related
    home_following_count = 0
    for user_id in following:
        try:
            user = _get_user(final_state_backend, user_id)
            if _check_user_category_relevance(user, "home"):
                home_following_count += 1
        except ValueError:
            continue
    
    if home_following_count < 2:
        return 0.0, f"Expected at least 2 home-related followed user(s), got {home_following_count}"

    # Check bookmarks count
    bookmarks = current_user.get("bookmarks", [])
    if not isinstance(bookmarks, list):
        return 0.0, "bookmarks is not a list"
    if len(bookmarks) < 3:
        return 0.0, f"Expected at least 3 bookmarked post(s), got {len(bookmarks)}"
    
    # Check if bookmarked posts are home-related
    home_bookmarks_count = 0
    for post_id in bookmarks:
        try:
            post = _get_post(final_state_backend, post_id)
            if _check_topic_relevance(post, "home"):
                home_bookmarks_count += 1
        except ValueError:
            continue
    
    if home_bookmarks_count < 3:
        return 0.0, f"Expected at least 3 home-related bookmarked posts, got {home_bookmarks_count}"

    # Check for album with at least 3 posts
    albums = current_user.get("albums", [])
    if not isinstance(albums, list):
        return 0.0, "albums is not a list"
    
    album_found = None
    for album in albums:
        post_ids = album.get("postIds", [])
        if isinstance(post_ids, list) and len(post_ids) >= 3:
            album_found = album
            break
    
    if not album_found:
        return 0.0, f"No album found with at least 3 posts"

    return 1.0, "Task completed successfully"


_validate_planning_redecorate_living_room: ValidateTask = {
    "state_key": {
        "users": {"collection": "users", "filter": {}},
        "posts": {"collection": "posts", "filter": {}},
    },
    "validate": _validate_planning_redecorate_living_room,
}


# =============================================================================
# Task 22: I keep seeing these amazing street style photos and want to improve my everyday ...
# =============================================================================

def _validate_keep_seeing_these_amazing(
    final_state_backend: Backend, final_state_frontend: Dict[str, Any]
) -> Tuple[float, str]:
    """Validate I keep seeing these amazing street style photos and want to ...
    
    Initial State Assumptions:
    - currentUser.bookmarks is empty [] before task starts
    """
    current_user_id = final_state_frontend.get("currentUserId", "0")
    if not current_user_id:
        return 0.0, "currentUserId missing in frontend state"
    
    try:
        current_user = _get_current_user(final_state_backend)
    except ValueError as e:
        return 0.0, str(e)
    
    # Check bookmarks count
    bookmarks = current_user.get("bookmarks", [])
    if not isinstance(bookmarks, list):
        return 0.0, "bookmarks is not a list"
    if len(bookmarks) < 4:
        return 0.0, f"Expected at least 4 bookmarked post(s), got {len(bookmarks)}"
    
    # Check if bookmarked posts are fashion-related
    fashion_bookmarks_count = 0
    for post_id in bookmarks:
        try:
            post = _get_post(final_state_backend, post_id)
            if _check_topic_relevance(post, "fashion"):
                fashion_bookmarks_count += 1
        except ValueError:
            continue
    
    if fashion_bookmarks_count < 4:
        return 0.0, f"Expected at least 4 fashion-related bookmarked posts, got {fashion_bookmarks_count}"

    return 1.0, "Task completed successfully"


_validate_keep_seeing_these_amazing: ValidateTask = {
    "state_key": {
        "users": {"collection": "users", "filter": {}},
        "posts": {"collection": "posts", "filter": {}},
    },
    "validate": _validate_keep_seeing_these_amazing,
}


# =============================================================================
# Task 23: My notifications are probably piling up and I should check what I've missed. Swi...
# =============================================================================

def _validate_notifications_are_probably_piling(
    final_state_backend: Backend, final_state_frontend: Dict[str, Any]
) -> Tuple[float, str]:
    """Validate My notifications are probably piling up and I should check w...
    """
    page = final_state_frontend.get("page")
    if page != "notifications":
        return 0.0, f"Expected page='notifications', got '{page}'"

    return 1.0, "Task completed successfully"


_validate_notifications_are_probably_piling: ValidateTask = {
    "state_key": {
    },
    "validate": _validate_notifications_are_probably_piling,
}


# =============================================================================
# Task 24: Looking for some meditation and wellness content to help with stress management....
# =============================================================================

def _validate_looking_for_some_meditation(
    final_state_backend: Backend, final_state_frontend: Dict[str, Any]
) -> Tuple[float, str]:
    """Validate Looking for some meditation and wellness content to help wit...
    
    Initial State Assumptions:
    - currentUser.following is empty [] before task starts
    - currentUser.bookmarks is empty [] before task starts
    """
    current_user_id = final_state_frontend.get("currentUserId", "0")
    if not current_user_id:
        return 0.0, "currentUserId missing in frontend state"
    
    try:
        current_user = _get_current_user(final_state_backend)
    except ValueError as e:
        return 0.0, str(e)
    
    # Check following count
    following = current_user.get("following", [])
    if not isinstance(following, list):
        return 0.0, "following is not a list"
    if len(following) < 1:
        return 0.0, f"Expected at least 1 followed user(s), got {len(following)}"
    
    # Check if followed users are wellness-related
    wellness_following_count = 0
    for user_id in following:
        try:
            user = _get_user(final_state_backend, user_id)
            if _check_user_category_relevance(user, "wellness"):
                wellness_following_count += 1
        except ValueError:
            continue
    
    if wellness_following_count < 1:
        return 0.0, f"Expected at least 1 wellness-related followed user(s), got {wellness_following_count}"

    # Check bookmarks count
    bookmarks = current_user.get("bookmarks", [])
    if not isinstance(bookmarks, list):
        return 0.0, "bookmarks is not a list"
    if len(bookmarks) < 3:
        return 0.0, f"Expected at least 3 bookmarked post(s), got {len(bookmarks)}"
    
    # Check if bookmarked posts are wellness-related
    wellness_bookmarks_count = 0
    for post_id in bookmarks:
        try:
            post = _get_post(final_state_backend, post_id)
            if _check_topic_relevance(post, "wellness"):
                wellness_bookmarks_count += 1
        except ValueError:
            continue
    
    if wellness_bookmarks_count < 3:
        return 0.0, f"Expected at least 3 wellness-related bookmarked posts, got {wellness_bookmarks_count}"

    return 1.0, "Task completed successfully"


_validate_looking_for_some_meditation: ValidateTask = {
    "state_key": {
        "users": {"collection": "users", "filter": {}},
        "posts": {"collection": "posts", "filter": {}},
    },
    "validate": _validate_looking_for_some_meditation,
}


# =============================================================================
# Task 25: Want to try making some traditional Chinese desserts but need recipes that aren'...
# =============================================================================

def _validate_want_try_making_some(
    final_state_backend: Backend, final_state_frontend: Dict[str, Any]
) -> Tuple[float, str]:
    """Validate Want to try making some traditional Chinese desserts but nee...
    
    Initial State Assumptions:
    - currentUser.bookmarks is empty [] before task starts
    """
    current_user_id = final_state_frontend.get("currentUserId", "0")
    if not current_user_id:
        return 0.0, "currentUserId missing in frontend state"
    
    try:
        current_user = _get_current_user(final_state_backend)
    except ValueError as e:
        return 0.0, str(e)
    
    page = final_state_frontend.get("page")
    if page != "search":
        return 0.0, f"Expected page='search', got '{page}'"
    search_query = final_state_frontend.get("searchQuery", "")
    if not search_query or "dessert".lower() not in search_query.lower():
        return 0.0, f"Expected search query containing 'dessert', got '{search_query}'"

    # Check bookmarks count
    bookmarks = current_user.get("bookmarks", [])
    if not isinstance(bookmarks, list):
        return 0.0, "bookmarks is not a list"
    if len(bookmarks) < 3:
        return 0.0, f"Expected at least 3 bookmarked post(s), got {len(bookmarks)}"
    
    # Check if bookmarked posts are food-related
    food_bookmarks_count = 0
    for post_id in bookmarks:
        try:
            post = _get_post(final_state_backend, post_id)
            if _check_topic_relevance(post, "food"):
                food_bookmarks_count += 1
        except ValueError:
            continue
    
    if food_bookmarks_count < 3:
        return 0.0, f"Expected at least 3 food-related bookmarked posts, got {food_bookmarks_count}"

    return 1.0, "Task completed successfully"


_validate_want_try_making_some: ValidateTask = {
    "state_key": {
        "users": {"collection": "users", "filter": {}},
        "posts": {"collection": "posts", "filter": {}},
    },
    "validate": _validate_want_try_making_some,
}


# =============================================================================
# Task 26: Saw someone post about their morning routine and it looked so peaceful. Find a l...
# =============================================================================

def _validate_saw_someone_post_about(
    final_state_backend: Backend, final_state_frontend: Dict[str, Any]
) -> Tuple[float, str]:
    """Validate Saw someone post about their morning routine and it looked s...
    
    Initial State Assumptions:
    - No comments from currentUser exist before task starts
    """
    current_user_id = final_state_frontend.get("currentUserId", "0")
    if not current_user_id:
        return 0.0, "currentUserId missing in frontend state"
    
    try:
        current_user = _get_current_user(final_state_backend)
    except ValueError as e:
        return 0.0, str(e)
    
    # Check for comment on lifestyle-related post
    # Query comments collection for comments by current user
    user_comments = final_state_backend.query({"collection": "comments", "filter": {"authorId": current_user_id}})
    lifestyle_comment_found = False
    
    for comment in user_comments:
        post_id = comment.get("postId")
        if not post_id:
            continue
        
        try:
            post = _get_post(final_state_backend, post_id)
            if _check_topic_relevance(post, "lifestyle"):
                lifestyle_comment_found = True
                break
        except ValueError:
            continue
    
    if not lifestyle_comment_found:
        return 0.0, "No comment found on lifestyle-related post"

    return 1.0, "Task completed successfully"


_validate_saw_someone_post_about: ValidateTask = {
    "state_key": {
        "users": {"collection": "users", "filter": {}},
        "posts": {"collection": "posts", "filter": {}},
        "comments": {"collection": "comments", "filter": {}},
    },
    "validate": _validate_saw_someone_post_about,
}


# =============================================================================
# Task 27: I'm trying to learn watercolor painting and need some beginner-friendly tutorial...
# =============================================================================

def _validate_trying_learn_watercolor_painting(
    final_state_backend: Backend, final_state_frontend: Dict[str, Any]
) -> Tuple[float, str]:
    """Validate I'm trying to learn watercolor painting and need some beginn...
    
    Initial State Assumptions:
    - currentUser.following is empty [] before task starts
    - currentUser.bookmarks is empty [] before task starts
    - currentUser.liked is empty [] before task starts
    """
    current_user_id = final_state_frontend.get("currentUserId", "0")
    if not current_user_id:
        return 0.0, "currentUserId missing in frontend state"
    
    try:
        current_user = _get_current_user(final_state_backend)
    except ValueError as e:
        return 0.0, str(e)
    
    # Check following count
    following = current_user.get("following", [])
    if not isinstance(following, list):
        return 0.0, "following is not a list"
    if len(following) < 2:
        return 0.0, f"Expected at least 2 followed user(s), got {len(following)}"
    
    # Check if followed users are art-related
    art_following_count = 0
    for user_id in following:
        try:
            user = _get_user(final_state_backend, user_id)
            if _check_user_category_relevance(user, "art"):
                art_following_count += 1
        except ValueError:
            continue
    
    if art_following_count < 2:
        return 0.0, f"Expected at least 2 art-related followed user(s), got {art_following_count}"

    # Check bookmarks or liked posts (at least 3)
    bookmarks = current_user.get("bookmarks", [])
    liked = current_user.get("liked", [])
    
    art_content_count = 0
    for post_id in list(bookmarks) + list(liked):
        try:
            post = _get_post(final_state_backend, post_id)
            if _check_topic_relevance(post, "art"):
                art_content_count += 1
        except ValueError:
            continue
    
    if art_content_count < 3:
        return 0.0, f"Expected at least 3 art-related bookmarked or liked posts, got {art_content_count}"

    return 1.0, "Task completed successfully"


_validate_trying_learn_watercolor_painting: ValidateTask = {
    "state_key": {
        "users": {"collection": "users", "filter": {}},
        "posts": {"collection": "posts", "filter": {}},
    },
    "validate": _validate_trying_learn_watercolor_painting,
}


# =============================================================================
# Task 28: Need some winter fashion inspiration that works for cold weather but still looks...
# =============================================================================

def _validate_need_some_winter_fashion(
    final_state_backend: Backend, final_state_frontend: Dict[str, Any]
) -> Tuple[float, str]:
    """Validate Need some winter fashion inspiration that works for cold wea...
    """
    return 1.0, "Task completed successfully"


_validate_need_some_winter_fashion: ValidateTask = {
    "state_key": {
    },
    "validate": _validate_need_some_winter_fashion,
}


# =============================================================================
# Task 29: My friend keeps talking about this productivity system she saw online. Search fo...
# =============================================================================

def _validate_friend_keeps_talking_about(
    final_state_backend: Backend, final_state_frontend: Dict[str, Any]
) -> Tuple[float, str]:
    """Validate My friend keeps talking about this productivity system she s...
    
    Initial State Assumptions:
    - currentUser.bookmarks is empty [] before task starts
    """
    current_user_id = final_state_frontend.get("currentUserId", "0")
    if not current_user_id:
        return 0.0, "currentUserId missing in frontend state"
    
    try:
        current_user = _get_current_user(final_state_backend)
    except ValueError as e:
        return 0.0, str(e)
    
    page = final_state_frontend.get("page")
    if page != "search":
        return 0.0, f"Expected page='search', got '{page}'"
    search_query = final_state_frontend.get("searchQuery", "")
    if not search_query or "productivity".lower() not in search_query.lower():
        return 0.0, f"Expected search query containing 'productivity', got '{search_query}'"

    # Check bookmarks count
    bookmarks = current_user.get("bookmarks", [])
    if not isinstance(bookmarks, list):
        return 0.0, "bookmarks is not a list"
    if len(bookmarks) < 3:
        return 0.0, f"Expected at least 3 bookmarked post(s), got {len(bookmarks)}"
    
    # Check if bookmarked posts are lifestyle-related
    lifestyle_bookmarks_count = 0
    for post_id in bookmarks:
        try:
            post = _get_post(final_state_backend, post_id)
            if _check_topic_relevance(post, "lifestyle"):
                lifestyle_bookmarks_count += 1
        except ValueError:
            continue
    
    if lifestyle_bookmarks_count < 3:
        return 0.0, f"Expected at least 3 lifestyle-related bookmarked posts, got {lifestyle_bookmarks_count}"

    return 1.0, "Task completed successfully"


_validate_friend_keeps_talking_about: ValidateTask = {
    "state_key": {
        "users": {"collection": "users", "filter": {}},
        "posts": {"collection": "posts", "filter": {}},
    },
    "validate": _validate_friend_keeps_talking_about,
}


# =============================================================================
# Task 30: I want to be more encouraging to content creators I follow. Go through my feed a...
# =============================================================================

def _validate_want_more_encouraging_content(
    final_state_backend: Backend, final_state_frontend: Dict[str, Any]
) -> Tuple[float, str]:
    """Validate I want to be more encouraging to content creators I follow. ...
    
    Initial State Assumptions:
    - No comments from currentUser exist before task starts
    """
    current_user_id = final_state_frontend.get("currentUserId", "0")
    if not current_user_id:
        return 0.0, "currentUserId missing in frontend state"
    
    try:
        current_user = _get_current_user(final_state_backend)
    except ValueError as e:
        return 0.0, str(e)
    
    # Check for comment on general-related post
    # Query comments collection for comments by current user
    user_comments = final_state_backend.query({"collection": "comments", "filter": {"authorId": current_user_id}})
    general_comment_found = False
    
    for comment in user_comments:
        post_id = comment.get("postId")
        if not post_id:
            continue
        
        try:
            post = _get_post(final_state_backend, post_id)
            if _check_topic_relevance(post, "general"):
                general_comment_found = True
                break
        except ValueError:
            continue
    
    if not general_comment_found:
        return 0.0, "No comment found on general-related post"

    return 1.0, "Task completed successfully"


_validate_want_more_encouraging_content: ValidateTask = {
    "state_key": {
        "users": {"collection": "users", "filter": {}},
        "posts": {"collection": "posts", "filter": {}},
        "comments": {"collection": "comments", "filter": {}},
    },
    "validate": _validate_want_more_encouraging_content,
}


# =============================================================================
# Task 31: Looking to upgrade my skincare routine without breaking the bank. Find posts abo...
# =============================================================================

def _validate_looking_upgrade_skincare_routine(
    final_state_backend: Backend, final_state_frontend: Dict[str, Any]
) -> Tuple[float, str]:
    """Validate Looking to upgrade my skincare routine without breaking the ...
    
    Initial State Assumptions:
    - currentUser.following is empty [] before task starts
    - currentUser.bookmarks is empty [] before task starts
    """
    current_user_id = final_state_frontend.get("currentUserId", "0")
    if not current_user_id:
        return 0.0, "currentUserId missing in frontend state"
    
    try:
        current_user = _get_current_user(final_state_backend)
    except ValueError as e:
        return 0.0, str(e)
    
    # Check following count
    following = current_user.get("following", [])
    if not isinstance(following, list):
        return 0.0, "following is not a list"
    if len(following) < 1:
        return 0.0, f"Expected at least 1 followed user(s), got {len(following)}"
    
    # Check if followed users are beauty-related
    beauty_following_count = 0
    for user_id in following:
        try:
            user = _get_user(final_state_backend, user_id)
            if _check_user_category_relevance(user, "beauty"):
                beauty_following_count += 1
        except ValueError:
            continue
    
    if beauty_following_count < 1:
        return 0.0, f"Expected at least 1 beauty-related followed user(s), got {beauty_following_count}"

    # Check bookmarks count
    bookmarks = current_user.get("bookmarks", [])
    if not isinstance(bookmarks, list):
        return 0.0, "bookmarks is not a list"
    if len(bookmarks) < 3:
        return 0.0, f"Expected at least 3 bookmarked post(s), got {len(bookmarks)}"
    
    # Check if bookmarked posts are beauty-related
    beauty_bookmarks_count = 0
    for post_id in bookmarks:
        try:
            post = _get_post(final_state_backend, post_id)
            if _check_topic_relevance(post, "beauty"):
                beauty_bookmarks_count += 1
        except ValueError:
            continue
    
    if beauty_bookmarks_count < 3:
        return 0.0, f"Expected at least 3 beauty-related bookmarked posts, got {beauty_bookmarks_count}"

    return 1.0, "Task completed successfully"


_validate_looking_upgrade_skincare_routine: ValidateTask = {
    "state_key": {
        "users": {"collection": "users", "filter": {}},
        "posts": {"collection": "posts", "filter": {}},
    },
    "validate": _validate_looking_upgrade_skincare_routine,
}


# =============================================================================
# Task 32: Planning a staycation in 上海 and want to discover hidden gems locals actually enj...
# =============================================================================

def _validate_planning_staycation_and_want(
    final_state_backend: Backend, final_state_frontend: Dict[str, Any]
) -> Tuple[float, str]:
    """Validate Planning a staycation in 上海 and want to discover hidden gems...
    
    Initial State Assumptions:
    - currentUser.bookmarks is empty [] before task starts
    """
    current_user_id = final_state_frontend.get("currentUserId", "0")
    if not current_user_id:
        return 0.0, "currentUserId missing in frontend state"
    
    try:
        current_user = _get_current_user(final_state_backend)
    except ValueError as e:
        return 0.0, str(e)
    
    page = final_state_frontend.get("page")
    if page != "search":
        return 0.0, f"Expected page='search', got '{page}'"
    search_query = final_state_frontend.get("searchQuery", "")
    if not search_query or "travel".lower() not in search_query.lower():
        return 0.0, f"Expected search query containing 'travel', got '{search_query}'"

    # Check bookmarks count
    bookmarks = current_user.get("bookmarks", [])
    if not isinstance(bookmarks, list):
        return 0.0, "bookmarks is not a list"
    if len(bookmarks) < 3:
        return 0.0, f"Expected at least 3 bookmarked post(s), got {len(bookmarks)}"
    
    # Check if bookmarked posts are travel-related
    travel_bookmarks_count = 0
    for post_id in bookmarks:
        try:
            post = _get_post(final_state_backend, post_id)
            if _check_topic_relevance(post, "travel"):
                travel_bookmarks_count += 1
        except ValueError:
            continue
    
    if travel_bookmarks_count < 3:
        return 0.0, f"Expected at least 3 travel-related bookmarked posts, got {travel_bookmarks_count}"

    return 1.0, "Task completed successfully"


_validate_planning_staycation_and_want: ValidateTask = {
    "state_key": {
        "users": {"collection": "users", "filter": {}},
        "posts": {"collection": "posts", "filter": {}},
    },
    "validate": _validate_planning_staycation_and_want,
}


# =============================================================================
# Task 33: I've been struggling with work-life balance and need some perspective from other...
# =============================================================================

def _validate_been_struggling_with_work(
    final_state_backend: Backend, final_state_frontend: Dict[str, Any]
) -> Tuple[float, str]:
    """Validate I've been struggling with work-life balance and need some pe...
    
    Initial State Assumptions:
    - No comments from currentUser exist before task starts
    """
    current_user_id = final_state_frontend.get("currentUserId", "0")
    if not current_user_id:
        return 0.0, "currentUserId missing in frontend state"
    
    try:
        current_user = _get_current_user(final_state_backend)
    except ValueError as e:
        return 0.0, str(e)
    
    # Check for comment on lifestyle-related post
    # Query comments collection for comments by current user
    user_comments = final_state_backend.query({"collection": "comments", "filter": {"authorId": current_user_id}})
    lifestyle_comment_found = False
    
    for comment in user_comments:
        post_id = comment.get("postId")
        if not post_id:
            continue
        
        try:
            post = _get_post(final_state_backend, post_id)
            if _check_topic_relevance(post, "lifestyle"):
                lifestyle_comment_found = True
                break
        except ValueError:
            continue
    
    if not lifestyle_comment_found:
        return 0.0, "No comment found on lifestyle-related post"

    return 1.0, "Task completed successfully"


_validate_been_struggling_with_work: ValidateTask = {
    "state_key": {
        "users": {"collection": "users", "filter": {}},
        "posts": {"collection": "posts", "filter": {}},
        "comments": {"collection": "comments", "filter": {}},
    },
    "validate": _validate_been_struggling_with_work,
}


# =============================================================================
# Task 34: Want to learn more about sustainable living without being preachy about it. Find...
# =============================================================================

def _validate_want_learn_more_about(
    final_state_backend: Backend, final_state_frontend: Dict[str, Any]
) -> Tuple[float, str]:
    """Validate Want to learn more about sustainable living without being pr...
    
    Initial State Assumptions:
    - currentUser.following is empty [] before task starts
    - currentUser.bookmarks is empty [] before task starts
    """
    current_user_id = final_state_frontend.get("currentUserId", "0")
    if not current_user_id:
        return 0.0, "currentUserId missing in frontend state"
    
    try:
        current_user = _get_current_user(final_state_backend)
    except ValueError as e:
        return 0.0, str(e)
    
    # Check following count
    following = current_user.get("following", [])
    if not isinstance(following, list):
        return 0.0, "following is not a list"
    if len(following) < 1:
        return 0.0, f"Expected at least 1 followed user(s), got {len(following)}"
    
    # Check if followed users are lifestyle-related
    lifestyle_following_count = 0
    for user_id in following:
        try:
            user = _get_user(final_state_backend, user_id)
            if _check_user_category_relevance(user, "lifestyle"):
                lifestyle_following_count += 1
        except ValueError:
            continue
    
    if lifestyle_following_count < 1:
        return 0.0, f"Expected at least 1 lifestyle-related followed user(s), got {lifestyle_following_count}"

    # Check bookmarks count
    bookmarks = current_user.get("bookmarks", [])
    if not isinstance(bookmarks, list):
        return 0.0, "bookmarks is not a list"
    if len(bookmarks) < 3:
        return 0.0, f"Expected at least 3 bookmarked post(s), got {len(bookmarks)}"
    
    # Check if bookmarked posts are lifestyle-related
    lifestyle_bookmarks_count = 0
    for post_id in bookmarks:
        try:
            post = _get_post(final_state_backend, post_id)
            if _check_topic_relevance(post, "lifestyle"):
                lifestyle_bookmarks_count += 1
        except ValueError:
            continue
    
    if lifestyle_bookmarks_count < 3:
        return 0.0, f"Expected at least 3 lifestyle-related bookmarked posts, got {lifestyle_bookmarks_count}"

    return 1.0, "Task completed successfully"


_validate_want_learn_more_about: ValidateTask = {
    "state_key": {
        "users": {"collection": "users", "filter": {}},
        "posts": {"collection": "posts", "filter": {}},
    },
    "validate": _validate_want_learn_more_about,
}


# =============================================================================
# Task 35: My apartment balcony is tiny but I want to try growing some plants. Search for s...
# =============================================================================

def _validate_apartment_balcony_tiny_but(
    final_state_backend: Backend, final_state_frontend: Dict[str, Any]
) -> Tuple[float, str]:
    """Validate My apartment balcony is tiny but I want to try growing some ...
    
    Initial State Assumptions:
    - currentUser.bookmarks is empty [] before task starts
    """
    current_user_id = final_state_frontend.get("currentUserId", "0")
    if not current_user_id:
        return 0.0, "currentUserId missing in frontend state"
    
    try:
        current_user = _get_current_user(final_state_backend)
    except ValueError as e:
        return 0.0, str(e)
    
    page = final_state_frontend.get("page")
    if page != "search":
        return 0.0, f"Expected page='search', got '{page}'"
    search_query = final_state_frontend.get("searchQuery", "")
    if not search_query or "gardening".lower() not in search_query.lower():
        return 0.0, f"Expected search query containing 'gardening', got '{search_query}'"

    # Check bookmarks count
    bookmarks = current_user.get("bookmarks", [])
    if not isinstance(bookmarks, list):
        return 0.0, "bookmarks is not a list"
    if len(bookmarks) < 3:
        return 0.0, f"Expected at least 3 bookmarked post(s), got {len(bookmarks)}"
    
    # Check if bookmarked posts are home-related
    home_bookmarks_count = 0
    for post_id in bookmarks:
        try:
            post = _get_post(final_state_backend, post_id)
            if _check_topic_relevance(post, "home"):
                home_bookmarks_count += 1
        except ValueError:
            continue
    
    if home_bookmarks_count < 3:
        return 0.0, f"Expected at least 3 home-related bookmarked posts, got {home_bookmarks_count}"

    return 1.0, "Task completed successfully"


_validate_apartment_balcony_tiny_but: ValidateTask = {
    "state_key": {
        "users": {"collection": "users", "filter": {}},
        "posts": {"collection": "posts", "filter": {}},
    },
    "validate": _validate_apartment_balcony_tiny_but,
}


# =============================================================================
# Task 36: I keep seeing these amazing baking posts and want to try making something simple...
# =============================================================================

def _validate_keep_seeing_these_amazing(
    final_state_backend: Backend, final_state_frontend: Dict[str, Any]
) -> Tuple[float, str]:
    """Validate I keep seeing these amazing baking posts and want to try mak...
    
    Initial State Assumptions:
    - No comments from currentUser exist before task starts
    """
    current_user_id = final_state_frontend.get("currentUserId", "0")
    if not current_user_id:
        return 0.0, "currentUserId missing in frontend state"
    
    try:
        current_user = _get_current_user(final_state_backend)
    except ValueError as e:
        return 0.0, str(e)
    
    # Check for comment on food-related post
    # Query comments collection for comments by current user
    user_comments = final_state_backend.query({"collection": "comments", "filter": {"authorId": current_user_id}})
    food_comment_found = False
    
    for comment in user_comments:
        post_id = comment.get("postId")
        if not post_id:
            continue
        
        try:
            post = _get_post(final_state_backend, post_id)
            if _check_topic_relevance(post, "food"):
                food_comment_found = True
                break
        except ValueError:
            continue
    
    if not food_comment_found:
        return 0.0, "No comment found on food-related post"

    return 1.0, "Task completed successfully"


_validate_keep_seeing_these_amazing: ValidateTask = {
    "state_key": {
        "users": {"collection": "users", "filter": {}},
        "posts": {"collection": "posts", "filter": {}},
        "comments": {"collection": "comments", "filter": {}},
    },
    "validate": _validate_keep_seeing_these_amazing,
}


# =============================================================================
# Task 37: Need some motivation for my fitness goals and want to follow people who share re...
# =============================================================================

def _validate_need_some_motivation_for(
    final_state_backend: Backend, final_state_frontend: Dict[str, Any]
) -> Tuple[float, str]:
    """Validate Need some motivation for my fitness goals and want to follow...
    
    Initial State Assumptions:
    - currentUser.following is empty [] before task starts
    - currentUser.bookmarks is empty [] before task starts
    """
    current_user_id = final_state_frontend.get("currentUserId", "0")
    if not current_user_id:
        return 0.0, "currentUserId missing in frontend state"
    
    try:
        current_user = _get_current_user(final_state_backend)
    except ValueError as e:
        return 0.0, str(e)
    
    # Check following count
    following = current_user.get("following", [])
    if not isinstance(following, list):
        return 0.0, "following is not a list"
    if len(following) < 2:
        return 0.0, f"Expected at least 2 followed user(s), got {len(following)}"
    
    # Check if followed users are fitness-related
    fitness_following_count = 0
    for user_id in following:
        try:
            user = _get_user(final_state_backend, user_id)
            if _check_user_category_relevance(user, "fitness"):
                fitness_following_count += 1
        except ValueError:
            continue
    
    if fitness_following_count < 2:
        return 0.0, f"Expected at least 2 fitness-related followed user(s), got {fitness_following_count}"

    # Check bookmarks count
    bookmarks = current_user.get("bookmarks", [])
    if not isinstance(bookmarks, list):
        return 0.0, "bookmarks is not a list"
    if len(bookmarks) < 2:
        return 0.0, f"Expected at least 2 bookmarked post(s), got {len(bookmarks)}"
    
    # Check if bookmarked posts are fitness-related
    fitness_bookmarks_count = 0
    for post_id in bookmarks:
        try:
            post = _get_post(final_state_backend, post_id)
            if _check_topic_relevance(post, "fitness"):
                fitness_bookmarks_count += 1
        except ValueError:
            continue
    
    if fitness_bookmarks_count < 2:
        return 0.0, f"Expected at least 2 fitness-related bookmarked posts, got {fitness_bookmarks_count}"

    return 1.0, "Task completed successfully"


_validate_need_some_motivation_for: ValidateTask = {
    "state_key": {
        "users": {"collection": "users", "filter": {}},
        "posts": {"collection": "posts", "filter": {}},
    },
    "validate": _validate_need_some_motivation_for,
}


# =============================================================================
# Task 38: I'm curious about that Creative Center feature I keep seeing mentioned. Check th...
# =============================================================================

def _validate_curious_about_that_creative(
    final_state_backend: Backend, final_state_frontend: Dict[str, Any]
) -> Tuple[float, str]:
    """Validate I'm curious about that Creative Center feature I keep seeing...
    """
    page_display_state = final_state_frontend.get("pageDisplayState")
    if page_display_state != "creative":
        return 0.0, f"Expected pageDisplayState='creative', got '{page_display_state}'"

    return 1.0, "Task completed successfully"


_validate_curious_about_that_creative: ValidateTask = {
    "state_key": {
    },
    "validate": _validate_curious_about_that_creative,
}


# =============================================================================
# Task 39: Looking for some book recommendations from people who have similar taste to mine...
# =============================================================================

def _validate_looking_for_some_book(
    final_state_backend: Backend, final_state_frontend: Dict[str, Any]
) -> Tuple[float, str]:
    """Validate Looking for some book recommendations from people who have s...
    
    Initial State Assumptions:
    - currentUser.following is empty [] before task starts
    """
    current_user_id = final_state_frontend.get("currentUserId", "0")
    if not current_user_id:
        return 0.0, "currentUserId missing in frontend state"
    
    try:
        current_user = _get_current_user(final_state_backend)
    except ValueError as e:
        return 0.0, str(e)
    
    # Check following count
    following = current_user.get("following", [])
    if not isinstance(following, list):
        return 0.0, "following is not a list"
    if len(following) < 1:
        return 0.0, f"Expected at least 1 followed user(s), got {len(following)}"
    
    # Check if followed users are culture-related
    culture_following_count = 0
    for user_id in following:
        try:
            user = _get_user(final_state_backend, user_id)
            if _check_user_category_relevance(user, "culture"):
                culture_following_count += 1
        except ValueError:
            continue
    
    if culture_following_count < 1:
        return 0.0, f"Expected at least 1 culture-related followed user(s), got {culture_following_count}"

    return 1.0, "Task completed successfully"


_validate_looking_for_some_book: ValidateTask = {
    "state_key": {
        "users": {"collection": "users", "filter": {}},
        "posts": {"collection": "posts", "filter": {}},
    },
    "validate": _validate_looking_for_some_book,
}


# =============================================================================
# Task 40: Want to try some new makeup techniques but I'm pretty basic with cosmetics. Sear...
# =============================================================================

def _validate_want_try_some_new(
    final_state_backend: Backend, final_state_frontend: Dict[str, Any]
) -> Tuple[float, str]:
    """Validate Want to try some new makeup techniques but I'm pretty basic ...
    
    Initial State Assumptions:
    - currentUser.bookmarks is empty [] before task starts
    """
    current_user_id = final_state_frontend.get("currentUserId", "0")
    if not current_user_id:
        return 0.0, "currentUserId missing in frontend state"
    
    try:
        current_user = _get_current_user(final_state_backend)
    except ValueError as e:
        return 0.0, str(e)
    
    page = final_state_frontend.get("page")
    if page != "search":
        return 0.0, f"Expected page='search', got '{page}'"
    search_query = final_state_frontend.get("searchQuery", "")
    if not search_query or "makeup".lower() not in search_query.lower():
        return 0.0, f"Expected search query containing 'makeup', got '{search_query}'"

    # Check bookmarks count
    bookmarks = current_user.get("bookmarks", [])
    if not isinstance(bookmarks, list):
        return 0.0, "bookmarks is not a list"
    if len(bookmarks) < 3:
        return 0.0, f"Expected at least 3 bookmarked post(s), got {len(bookmarks)}"
    
    # Check if bookmarked posts are beauty-related
    beauty_bookmarks_count = 0
    for post_id in bookmarks:
        try:
            post = _get_post(final_state_backend, post_id)
            if _check_topic_relevance(post, "beauty"):
                beauty_bookmarks_count += 1
        except ValueError:
            continue
    
    if beauty_bookmarks_count < 3:
        return 0.0, f"Expected at least 3 beauty-related bookmarked posts, got {beauty_bookmarks_count}"

    return 1.0, "Task completed successfully"


_validate_want_try_some_new: ValidateTask = {
    "state_key": {
        "users": {"collection": "users", "filter": {}},
        "posts": {"collection": "posts", "filter": {}},
    },
    "validate": _validate_want_try_some_new,
}


# =============================================================================
# Task 41: Someone posted gorgeous photos from their recent trip and I want to know more ab...
# =============================================================================

def _validate_someone_posted_gorgeous_photos(
    final_state_backend: Backend, final_state_frontend: Dict[str, Any]
) -> Tuple[float, str]:
    """Validate Someone posted gorgeous photos from their recent trip and I ...
    
    Initial State Assumptions:
    - No comments from currentUser exist before task starts
    """
    current_user_id = final_state_frontend.get("currentUserId", "0")
    if not current_user_id:
        return 0.0, "currentUserId missing in frontend state"
    
    try:
        current_user = _get_current_user(final_state_backend)
    except ValueError as e:
        return 0.0, str(e)
    
    # Check for comment on travel-related post
    # Query comments collection for comments by current user
    user_comments = final_state_backend.query({"collection": "comments", "filter": {"authorId": current_user_id}})
    travel_comment_found = False
    
    for comment in user_comments:
        post_id = comment.get("postId")
        if not post_id:
            continue
        
        try:
            post = _get_post(final_state_backend, post_id)
            if _check_topic_relevance(post, "travel"):
                travel_comment_found = True
                break
        except ValueError:
            continue
    
    if not travel_comment_found:
        return 0.0, "No comment found on travel-related post"

    return 1.0, "Task completed successfully"


_validate_someone_posted_gorgeous_photos: ValidateTask = {
    "state_key": {
        "users": {"collection": "users", "filter": {}},
        "posts": {"collection": "posts", "filter": {}},
        "comments": {"collection": "comments", "filter": {}},
    },
    "validate": _validate_someone_posted_gorgeous_photos,
}


# =============================================================================
# Task 42: I'm trying to develop better morning habits and need some realistic routine insp...
# =============================================================================

def _validate_trying_develop_better_morning(
    final_state_backend: Backend, final_state_frontend: Dict[str, Any]
) -> Tuple[float, str]:
    """Validate I'm trying to develop better morning habits and need some re...
    """
    return 1.0, "Task completed successfully"


_validate_trying_develop_better_morning: ValidateTask = {
    "state_key": {
    },
    "validate": _validate_trying_develop_better_morning,
}


# =============================================================================
# Task 43: My workspace at home is pretty chaotic and I need better organization ideas. Loo...
# =============================================================================

def _validate_workspace_home_pretty_chaotic(
    final_state_backend: Backend, final_state_frontend: Dict[str, Any]
) -> Tuple[float, str]:
    """Validate My workspace at home is pretty chaotic and I need better org...
    
    Initial State Assumptions:
    - currentUser.following is empty [] before task starts
    - currentUser.bookmarks is empty [] before task starts
    """
    current_user_id = final_state_frontend.get("currentUserId", "0")
    if not current_user_id:
        return 0.0, "currentUserId missing in frontend state"
    
    try:
        current_user = _get_current_user(final_state_backend)
    except ValueError as e:
        return 0.0, str(e)
    
    # Check following count
    following = current_user.get("following", [])
    if not isinstance(following, list):
        return 0.0, "following is not a list"
    if len(following) < 1:
        return 0.0, f"Expected at least 1 followed user(s), got {len(following)}"
    
    # Check if followed users are home-related
    home_following_count = 0
    for user_id in following:
        try:
            user = _get_user(final_state_backend, user_id)
            if _check_user_category_relevance(user, "home"):
                home_following_count += 1
        except ValueError:
            continue
    
    if home_following_count < 1:
        return 0.0, f"Expected at least 1 home-related followed user(s), got {home_following_count}"

    # Check bookmarks count
    bookmarks = current_user.get("bookmarks", [])
    if not isinstance(bookmarks, list):
        return 0.0, "bookmarks is not a list"
    if len(bookmarks) < 3:
        return 0.0, f"Expected at least 3 bookmarked post(s), got {len(bookmarks)}"
    
    # Check if bookmarked posts are home-related
    home_bookmarks_count = 0
    for post_id in bookmarks:
        try:
            post = _get_post(final_state_backend, post_id)
            if _check_topic_relevance(post, "home"):
                home_bookmarks_count += 1
        except ValueError:
            continue
    
    if home_bookmarks_count < 3:
        return 0.0, f"Expected at least 3 home-related bookmarked posts, got {home_bookmarks_count}"

    return 1.0, "Task completed successfully"


_validate_workspace_home_pretty_chaotic: ValidateTask = {
    "state_key": {
        "users": {"collection": "users", "filter": {}},
        "posts": {"collection": "posts", "filter": {}},
    },
    "validate": _validate_workspace_home_pretty_chaotic,
}


# =============================================================================
# Task 44: I want to be more active in supporting artists and creators I discover. Browse t...
# =============================================================================

def _validate_want_more_active_supporting(
    final_state_backend: Backend, final_state_frontend: Dict[str, Any]
) -> Tuple[float, str]:
    """Validate I want to be more active in supporting artists and creators ...
    
    Initial State Assumptions:
    - No comments from currentUser exist before task starts
    """
    current_user_id = final_state_frontend.get("currentUserId", "0")
    if not current_user_id:
        return 0.0, "currentUserId missing in frontend state"
    
    try:
        current_user = _get_current_user(final_state_backend)
    except ValueError as e:
        return 0.0, str(e)
    
    # Check for comment on art-related post
    # Query comments collection for comments by current user
    user_comments = final_state_backend.query({"collection": "comments", "filter": {"authorId": current_user_id}})
    art_comment_found = False
    
    for comment in user_comments:
        post_id = comment.get("postId")
        if not post_id:
            continue
        
        try:
            post = _get_post(final_state_backend, post_id)
            if _check_topic_relevance(post, "art"):
                art_comment_found = True
                break
        except ValueError:
            continue
    
    if not art_comment_found:
        return 0.0, "No comment found on art-related post"

    return 1.0, "Task completed successfully"


_validate_want_more_active_supporting: ValidateTask = {
    "state_key": {
        "users": {"collection": "users", "filter": {}},
        "posts": {"collection": "posts", "filter": {}},
        "comments": {"collection": "comments", "filter": {}},
    },
    "validate": _validate_want_more_active_supporting,
}


# =============================================================================
# Task 45: Looking for some easy weeknight dinner ideas that don't require tons of prep tim...
# =============================================================================

def _validate_looking_for_some_easy(
    final_state_backend: Backend, final_state_frontend: Dict[str, Any]
) -> Tuple[float, str]:
    """Validate Looking for some easy weeknight dinner ideas that don't requ...
    
    Initial State Assumptions:
    - currentUser.bookmarks is empty [] before task starts
    """
    current_user_id = final_state_frontend.get("currentUserId", "0")
    if not current_user_id:
        return 0.0, "currentUserId missing in frontend state"
    
    try:
        current_user = _get_current_user(final_state_backend)
    except ValueError as e:
        return 0.0, str(e)
    
    page = final_state_frontend.get("page")
    if page != "search":
        return 0.0, f"Expected page='search', got '{page}'"
    search_query = final_state_frontend.get("searchQuery", "")
    if not search_query or "quick".lower() not in search_query.lower():
        return 0.0, f"Expected search query containing 'quick', got '{search_query}'"

    # Check bookmarks count
    bookmarks = current_user.get("bookmarks", [])
    if not isinstance(bookmarks, list):
        return 0.0, "bookmarks is not a list"
    if len(bookmarks) < 4:
        return 0.0, f"Expected at least 4 bookmarked post(s), got {len(bookmarks)}"
    
    # Check if bookmarked posts are food-related
    food_bookmarks_count = 0
    for post_id in bookmarks:
        try:
            post = _get_post(final_state_backend, post_id)
            if _check_topic_relevance(post, "food"):
                food_bookmarks_count += 1
        except ValueError:
            continue
    
    if food_bookmarks_count < 4:
        return 0.0, f"Expected at least 4 food-related bookmarked posts, got {food_bookmarks_count}"

    return 1.0, "Task completed successfully"


_validate_looking_for_some_easy: ValidateTask = {
    "state_key": {
        "users": {"collection": "users", "filter": {}},
        "posts": {"collection": "posts", "filter": {}},
    },
    "validate": _validate_looking_for_some_easy,
}


# =============================================================================
# Task 46: I've been thinking about trying yoga but feel intimidated by all the advanced po...
# =============================================================================

def _validate_been_thinking_about_trying(
    final_state_backend: Backend, final_state_frontend: Dict[str, Any]
) -> Tuple[float, str]:
    """Validate I've been thinking about trying yoga but feel intimidated by...
    
    Initial State Assumptions:
    - currentUser.following is empty [] before task starts
    - currentUser.bookmarks is empty [] before task starts
    """
    current_user_id = final_state_frontend.get("currentUserId", "0")
    if not current_user_id:
        return 0.0, "currentUserId missing in frontend state"
    
    try:
        current_user = _get_current_user(final_state_backend)
    except ValueError as e:
        return 0.0, str(e)
    
    # Check following count
    following = current_user.get("following", [])
    if not isinstance(following, list):
        return 0.0, "following is not a list"
    if len(following) < 1:
        return 0.0, f"Expected at least 1 followed user(s), got {len(following)}"
    
    # Check if followed users are fitness-related
    fitness_following_count = 0
    for user_id in following:
        try:
            user = _get_user(final_state_backend, user_id)
            if _check_user_category_relevance(user, "fitness"):
                fitness_following_count += 1
        except ValueError:
            continue
    
    if fitness_following_count < 1:
        return 0.0, f"Expected at least 1 fitness-related followed user(s), got {fitness_following_count}"

    # Check bookmarks count
    bookmarks = current_user.get("bookmarks", [])
    if not isinstance(bookmarks, list):
        return 0.0, "bookmarks is not a list"
    if len(bookmarks) < 3:
        return 0.0, f"Expected at least 3 bookmarked post(s), got {len(bookmarks)}"
    
    # Check if bookmarked posts are fitness-related
    fitness_bookmarks_count = 0
    for post_id in bookmarks:
        try:
            post = _get_post(final_state_backend, post_id)
            if _check_topic_relevance(post, "fitness"):
                fitness_bookmarks_count += 1
        except ValueError:
            continue
    
    if fitness_bookmarks_count < 3:
        return 0.0, f"Expected at least 3 fitness-related bookmarked posts, got {fitness_bookmarks_count}"

    return 1.0, "Task completed successfully"


_validate_been_thinking_about_trying: ValidateTask = {
    "state_key": {
        "users": {"collection": "users", "filter": {}},
        "posts": {"collection": "posts", "filter": {}},
    },
    "validate": _validate_been_thinking_about_trying,
}


# =============================================================================
# Task 47: Want to update my wardrobe with some versatile pieces that work for multiple occ...
# =============================================================================

def _validate_want_update_wardrobe_with(
    final_state_backend: Backend, final_state_frontend: Dict[str, Any]
) -> Tuple[float, str]:
    """Validate Want to update my wardrobe with some versatile pieces that w...
    
    Initial State Assumptions:
    - currentUser.bookmarks is empty [] before task starts
    """
    current_user_id = final_state_frontend.get("currentUserId", "0")
    if not current_user_id:
        return 0.0, "currentUserId missing in frontend state"
    
    try:
        current_user = _get_current_user(final_state_backend)
    except ValueError as e:
        return 0.0, str(e)
    
    # Check bookmarks count
    bookmarks = current_user.get("bookmarks", [])
    if not isinstance(bookmarks, list):
        return 0.0, "bookmarks is not a list"
    if len(bookmarks) < 4:
        return 0.0, f"Expected at least 4 bookmarked post(s), got {len(bookmarks)}"
    
    # Check if bookmarked posts are fashion-related
    fashion_bookmarks_count = 0
    for post_id in bookmarks:
        try:
            post = _get_post(final_state_backend, post_id)
            if _check_topic_relevance(post, "fashion"):
                fashion_bookmarks_count += 1
        except ValueError:
            continue
    
    if fashion_bookmarks_count < 4:
        return 0.0, f"Expected at least 4 fashion-related bookmarked posts, got {fashion_bookmarks_count}"

    return 1.0, "Task completed successfully"


_validate_want_update_wardrobe_with: ValidateTask = {
    "state_key": {
        "users": {"collection": "users", "filter": {}},
        "posts": {"collection": "posts", "filter": {}},
    },
    "validate": _validate_want_update_wardrobe_with,
}


# =============================================================================
# Task 48: I keep forgetting to check my liked posts section to revisit things I saved earl...
# =============================================================================

def _validate_keep_forgetting_check_liked(
    final_state_backend: Backend, final_state_frontend: Dict[str, Any]
) -> Tuple[float, str]:
    """Validate I keep forgetting to check my liked posts section to revisit...
    """
    page = final_state_frontend.get("page")
    if page != "profile":
        return 0.0, f"Expected page='profile', got '{page}'"
    profile_view = final_state_frontend.get("profileView")
    if profile_view != "bookmarks":
        return 0.0, f"Expected profileView='bookmarks', got '{profile_view}'"

    return 1.0, "Task completed successfully"


_validate_keep_forgetting_check_liked: ValidateTask = {
    "state_key": {
    },
    "validate": _validate_keep_forgetting_check_liked,
}


# =============================================================================
# Task 49: Looking for some photography inspiration and tips to improve my own pictures. Fi...
# =============================================================================

def _validate_looking_for_some_photography(
    final_state_backend: Backend, final_state_frontend: Dict[str, Any]
) -> Tuple[float, str]:
    """Validate Looking for some photography inspiration and tips to improve...
    
    Initial State Assumptions:
    - currentUser.following is empty [] before task starts
    - currentUser.bookmarks is empty [] before task starts
    """
    current_user_id = final_state_frontend.get("currentUserId", "0")
    if not current_user_id:
        return 0.0, "currentUserId missing in frontend state"
    
    try:
        current_user = _get_current_user(final_state_backend)
    except ValueError as e:
        return 0.0, str(e)
    
    # Check following count
    following = current_user.get("following", [])
    if not isinstance(following, list):
        return 0.0, "following is not a list"
    if len(following) < 1:
        return 0.0, f"Expected at least 1 followed user(s), got {len(following)}"
    
    # Check if followed users are art-related
    art_following_count = 0
    for user_id in following:
        try:
            user = _get_user(final_state_backend, user_id)
            if _check_user_category_relevance(user, "art"):
                art_following_count += 1
        except ValueError:
            continue
    
    if art_following_count < 1:
        return 0.0, f"Expected at least 1 art-related followed user(s), got {art_following_count}"

    # Check bookmarks count
    bookmarks = current_user.get("bookmarks", [])
    if not isinstance(bookmarks, list):
        return 0.0, "bookmarks is not a list"
    if len(bookmarks) < 3:
        return 0.0, f"Expected at least 3 bookmarked post(s), got {len(bookmarks)}"
    
    # Check if bookmarked posts are art-related
    art_bookmarks_count = 0
    for post_id in bookmarks:
        try:
            post = _get_post(final_state_backend, post_id)
            if _check_topic_relevance(post, "art"):
                art_bookmarks_count += 1
        except ValueError:
            continue
    
    if art_bookmarks_count < 3:
        return 0.0, f"Expected at least 3 art-related bookmarked posts, got {art_bookmarks_count}"

    return 1.0, "Task completed successfully"


_validate_looking_for_some_photography: ValidateTask = {
    "state_key": {
        "users": {"collection": "users", "filter": {}},
        "posts": {"collection": "posts", "filter": {}},
    },
    "validate": _validate_looking_for_some_photography,
}


# =============================================================================
# Task 50: Someone shared a really helpful study technique that I want to remember for late...
# =============================================================================

def _validate_someone_shared_really_helpful(
    final_state_backend: Backend, final_state_frontend: Dict[str, Any]
) -> Tuple[float, str]:
    """Validate Someone shared a really helpful study technique that I want ...
    
    Initial State Assumptions:
    - currentUser.bookmarks is empty [] before task starts
    """
    current_user_id = final_state_frontend.get("currentUserId", "0")
    if not current_user_id:
        return 0.0, "currentUserId missing in frontend state"
    
    try:
        current_user = _get_current_user(final_state_backend)
    except ValueError as e:
        return 0.0, str(e)
    
    # Check bookmarks count
    bookmarks = current_user.get("bookmarks", [])
    if not isinstance(bookmarks, list):
        return 0.0, "bookmarks is not a list"
    if len(bookmarks) < 3:
        return 0.0, f"Expected at least 3 bookmarked post(s), got {len(bookmarks)}"
    
    # Check if bookmarked posts are education-related
    education_bookmarks_count = 0
    for post_id in bookmarks:
        try:
            post = _get_post(final_state_backend, post_id)
            if _check_topic_relevance(post, "education"):
                education_bookmarks_count += 1
        except ValueError:
            continue
    
    if education_bookmarks_count < 3:
        return 0.0, f"Expected at least 3 education-related bookmarked posts, got {education_bookmarks_count}"

    return 1.0, "Task completed successfully"


_validate_someone_shared_really_helpful: ValidateTask = {
    "state_key": {
        "users": {"collection": "users", "filter": {}},
        "posts": {"collection": "posts", "filter": {}},
    },
    "validate": _validate_someone_shared_really_helpful,
}
