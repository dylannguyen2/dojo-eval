// scripts/xhs-generate-tasks.js
// Run: node scripts/xhs-generate-tasks.js
// Input: xhs-db-context.json
// Output: xhs-generated-tasks.json

const Anthropic = require('@anthropic-ai/sdk');
const fs = require('fs');

const client = new Anthropic();

function formatContextForPrompt(ctx) {
  return `
## Available Data in Mock XiaoHongShu Environment

**User Categories:**
${ctx.userCategories.slice(0, 20).map(c => `- ${c.category} (${c.count} users)`).join('\n')}

**Post Tags (${ctx.postTags.length} unique tags):**
${ctx.postTags.slice(0, 50).map(t => `- ${t.tag} (${t.count} posts)`).join('\n')}

**Tag Themes with Sample Posts:**
${ctx.tagThemes.slice(0, 25).map(t => {
  const samples = t.samplePosts.map(p => `"${p.title}"`).join(', ');
  return `- ${t.tag} (${t.count} posts, ${t.totalLikes} total likes) — e.g., ${samples}`;
}).join('\n')}

**Post Locations:**
${ctx.postLocations.slice(0, 20).map(l => `- ${l.location} (${l.count} posts)`).join('\n')}

**Posts by Type:**
${ctx.postsByType.map(t => `- ${t._id}: ${t.count} posts (avg ${Math.round(t.avgLikes)} likes, ${Math.round(t.avgBookmarks)} bookmarks)`).join('\n')}

**Users (${ctx.users.length} total):**
${ctx.users.slice(0, 25).map(u => `- "${u.displayName}" (@${u.username}) — Category: ${u.category || 'N/A'}, Location: ${u.location || 'N/A'} — Bio: ${(u.bio || '').substring(0, 40)}`).join('\n')}

**User Locations:**
${ctx.userLocations.slice(0, 15).map(l => `- ${l.location} (${l.count} users)`).join('\n')}

**Existing Album/Collection Names:**
${ctx.albumNames.slice(0, 20).map(a => `- "${a.name}" (${a.count} occurrences)`).join('\n')}

**Sample Albums with Details:**
${ctx.albums.slice(0, 15).map(a => `- "${a.albumName}" ${a.isPublic ? '(public)' : '(private)'} — ${a.postCount} posts — ${a.albumDescription || 'no description'}`).join('\n')}

**Sample Image Posts:**
${ctx.imagePosts.slice(0, 15).map(p => `- "${p.title}" — Tags: ${p.tags.slice(0, 5).join(', ')} — ${p.likes} likes, ${p.bookmarks} bookmarks ${p.location ? `(${p.location})` : ''}`).join('\n')}

**Sample Video Posts:**
${ctx.videoPosts.slice(0, 15).map(p => `- "${p.title}" — Tags: ${p.tags.slice(0, 5).join(', ')} — ${p.likes} likes, ${p.bookmarks} bookmarks ${p.location ? `(${p.location})` : ''}`).join('\n')}

**High Engagement Posts:**
${ctx.highEngagementPosts.slice(0, 15).map(p => `- "${p.title}" (${p.type}) — Tags: ${p.tags.slice(0, 4).join(', ')} — ${p.likes} likes, ${p.bookmarks} bookmarks`).join('\n')}

**Sample Comments:**
${ctx.sampleComments.slice(0, 10).map(c => `- On "${c.postTitle}": "${c.commentContent}" (${c.likeCount} likes)`).join('\n')}

**Search History Queries:**
${ctx.searchHistory.slice(0, 15).map(q => `- "${q}"`).join('\n')}

**Notification Types:**
${ctx.notificationPatterns.slice(0, 10).map(n => `- ${n.category}/${n.type}: ${n.count} notifications`).join('\n')}

**Users by Content Specialty:**
${ctx.usersBySpecialty.slice(0, 15).map(u => {
  const tags = u.topTags.map(t => `${t.tag}(${t.count})`).join(', ');
  return `- User ${u.userId.substring(0, 8)}...: ${tags}`;
}).join('\n')}

**Social Graph Sample:**
${ctx.socialGraphSample.map(u => `- "${u.displayName}" (${u.category || 'N/A'}): ${u.followersCount} followers, ${u.followingCount} following, ${u.postsCount} posts`).join('\n')}

---
⚠️ CRITICAL CONSTRAINTS:
1. ONLY reference tags that exist in the post tags list above
2. ONLY reference user categories from the user categories list
3. Location names should match locations in the data
4. Album/collection names should be realistic Chinese names similar to existing ones
5. For tasks involving specific content themes, USE the tags and themes listed above
6. User display names and usernames should come from the users list
7. Do NOT invent tags, locations, or users that aren't in this data
`;
}

// ============================================================
// PASTE YOUR SYSTEM PROMPT BELOW (between the backticks)
// This is the base system prompt - context will be appended
// ============================================================
const BASE_SYSTEM_PROMPT = `# Task: Generate User Prompts for XiaoHongShu Agent Evaluation

## App Capabilities

---BEGIN CAPABILITIES---
## Environment Overview

**Target Website:** XiaoHongShu

**Environment Type:** Fully mocked, programmable web application

**Key Characteristics:**

- High-value Chinese social commerce platform
- Visual content discovery (lifestyle, fashion, beauty, travel)
- User-generated content (UGC) with product recommendations
- Collections and bookmarking system
- Creator profiles and following mechanism
- Rich multimedia posts with engagement features

---

## Core Workflows

### Workflow 1: Content Discovery & Search

**User Goal:** Discover lifestyle content and products through search, browse, and filtering

**Key Interactions:**

1. **Homepage Exploration**
    - 🟩 View feed with posts from various creators
    - 🟩 Browse visual content (videos, images)
    - 🟩 Click posts to open detailed post modal/dialog
    - 🟩 Scroll through homepage feed
    - 🟩 Apply quick filters on homepage
    - 🟩 Navigate using logo to return to homepage
2. **Search Functionality**
    - 🟩 Enter search queries in search input
    - 🟩 View search results (posts)
    - 🟩 Switch to Users section in search results
    - 🟩 Browse creator/user results
    - 🟩 Click posts from search results to view details
    - 🟩 Apply filters in search results
3. **Post Detail Interaction**
    - 🟩 View post in modal/dialog overlay
    - 🟩 View post content (video, images, text, descriptions)
    - 🟩 Click user/creator to navigate to profile
    - 🟩 Access share functionality dropdown
    - 🟩 Close modal to return to previous view

**Success Criteria:**

- Agent can discover content through multiple pathways (homepage, search, filters)
- Search allows switching between content and user results
- Post modals display without navigation disruption
- Filtering works on homepage and search results
- All navigation maintains context and state

---

### Workflow 2: User Profile & Social Graph

**User Goal:** Explore creator profiles, follow users, and manage social connections

**Key Interactions:**

1. **Profile Navigation**
    - 🟩 Navigate to creator profiles from posts
    - 🟩 Navigate to creator profiles from search results
    - 🟩 View creator profile page
    - 🟩 View creator's content on profile
    - 🟩 Browse creator's post history
2. **Follow Management**
    - 🟩 Follow creators via \"关注\" (Follow) button
    - 🟩 Unfollow creators
    - 🟩 View followed users' content
    - 🟩 View follower/following counts
3. **Current User Profile**
    - 🟩 View own profile via profile picture
    - 🟩 Access Collections section
    - 🟩 Access Liked section
    - 🟩 View collected posts in Collections
    - 🟩 View liked posts in Liked section
    - 🟩 Manage album collections
    - 🟩 Organize saved content

**Success Criteria:**

- Profile pages display creator content accurately
- Follow actions update immediately
- Current user profile shows collected and liked content
- Collections organize content effectively
- Navigation between profiles and feed is seamless

---

### Workflow 3: Content Engagement & Personalization

**User Goal:** Engage with content through likes, comments, bookmarks, and receive personalized updates

**Key Interactions:**

1. **Post Engagement**
    - 🟩 Like posts from detail modal
    - 🟩 Unlike posts
    - 🟩 Bookmark/collect posts
    - 🟩 Remove from bookmarks
    - 🟩 Comment on posts
    - 🟩 Reply to comments
    - 🟩 Like comments
    - 🟩 Share posts via share dropdown
2. **Notifications & Activity**
    - 🟩 Access notifications page
    - 🟩 View recent followers
    - 🟩 View recent mentions
    - 🟩 View recent likes on comments
    - 🟩 Mark notifications as read
    - 🟩 Navigate from notifications to source content
3. **Personalization & Settings**
    - 🟩 Access settings via \"more\" dropdown/popup
    - 🟩 Change app theme (System, Light, Dark)
    - 🟩 Access Creative Center dropdown
    - 🟩 Access Business Cooperation dropdown
    - 🟩 Use Creative Center features
    - 🟩 Scroll left sidebar to view XiaoHongShu licenses

**Success Criteria:**

- Engagement actions (like, bookmark, comment) persist
- Notifications accurately reflect user activity
- Theme switching works across all pages
- Collections organize content effectively
- Settings and preferences save correctly

---END CAPABILITIES---

## Verifiable End States
The agent's success can ONLY be verified via a final snapshot of the app. Valid verifiable states:

- **Collections**: A collection with a specific name exists and contains bookmarked posts
- **Following**: User is following specific accounts (visible on profile or following list)
- **Likes**: Posts appear in user's Liked section
- **Comments**: A comment with specific text exists on a post
- **Theme**: App is in light/dark/system mode
- **Current screen**: User is on a specific page (profile, notifications, settings, search results, post modal, etc.)
- **Notifications**: Notifications page is visible, notifications marked as read

**NOT verifiable (avoid prompts that rely solely on these):**
- Navigation history or pages visited during the task
- Feed algorithm or recommendation changes
- \"Discovery\" or \"exploration\" as an outcome
- Agent's internal observations or summaries
- Transient UI states that don't persist`;

// ============================================================

// ============================================================
// PASTE YOUR USER PROMPT BELOW (between the backticks)
// ============================================================
const USER_PROMPT_TEMPLATE = `Generate 50 task prompts for a computer-use agent operating XiaoHongShu.

## Style Requirements

**Voice & Tone:**
- Sound like a real person casually asking an assistant for help
- Vary sentence structure—don't always start with \"I\" 
- Use natural quantities (\"some\", \"a few\", \"a handful\") not exact numbers

**Structure:**
- Embed rich context that establishes a real situation or motivation
- Include taste/preference constraints that feel human (\"not too touristy\", \"realistic not fancy\", \"cozy not corporate\")
- Combine multiple related actions naturally (e.g., save posts AND follow creators)
- Express the desired outcome as a goal, not a procedure

**Complexity:**
- Each prompt should involve 2-3 verifiable actions
- Cover different workflows: content discovery, profiles/social, engagement, settings
- Vary the specificity—some prompts very targeted, others more open-ended

## Output Format

For each prompt, provide:
1. The natural language prompt
2. Verification criteria in parentheses with concrete, measurable outcomes

## Examples

Prompt: \"I need outfit inspiration for an upcoming job interview in a creative industry—professional but not too formal. Collect outfit posts that match the aesthetic I'm looking for, and follow some fashion creators whose style resonates.\"
Verification: (Collection exists with fashion/outfit/interview-related name containing ≥3 posts; user following ≥2 fashion-related accounts)

Prompt: \"Planning a trip to Chengdu next month and want to save food spots locals actually recommend, not just tourist traps. Bookmark the good finds and follow a few food bloggers who seem to know the city well.\"
Verification: (Collection with Chengdu/food-related name containing ≥3 posts; user following ≥2 accounts posting Chengdu food content)

Prompt: \"My apartment feels so cluttered and I've been getting into minimalism lately. Set me up with some home organization content—save posts with practical tips and find creators who do realistic small-space organizing, not those huge fancy houses.\"
Verification: (Collection with minimalism/organization-related name containing ≥3 posts; user following ≥2 home organization/minimalist accounts)

Prompt: \"Saw a really beautiful watercolor painting on my feed earlier and want to leave an encouraging comment for the artist. Find an art post and say something supportive.\"
Verification: (Comment exists on an art-related post containing encouraging/positive sentiment)

Prompt: \"This bright white screen is killing me at night—switch to dark mode and then check if I have any new notifications while you're at it.\"
Verification: (Theme = Dark; user is on notifications page or notifications have been viewed)

---

Now generate 50 prompts. Ensure prompts are in english (can use chinese terminology if necessary) and have variety across:
- Workflows (discovery, social/profiles, engagement, settings)
- Action combinations (collect+follow, search+save, comment+like, settings+navigation)
- Topic areas (fashion, food, travel, beauty, fitness, home, pets, art, tech, etc.)`;
// ============================================================

// Additional instructions appended to user prompt for JSON output
const OUTPUT_FORMAT_INSTRUCTIONS = `

## Output Format

Return a JSON array where each element has:
- "prompt": the natural language task prompt
- "verification": concrete, measurable success criteria
- "workflow": one of "content_discovery", "social_profiles", "content_engagement", "settings_personalization"
- "topic_area": the primary topic (e.g., "fashion", "food", "travel", "beauty", etc.)

Return ONLY the JSON array, no other text.`;

async function generateTasks() {
  // Load context
  if (!fs.existsSync('xhs-db-context.json')) {
    console.error('❌ xhs-db-context.json not found. Run xhs-extract-context.js first.');
    process.exit(1);
  }
  
  const context = JSON.parse(fs.readFileSync('xhs-db-context.json', 'utf8'));
  console.log('Loaded context from xhs-db-context.json');
  console.log(`  - ${context.users.length} users`);
  console.log(`  - ${context.summary.totalPosts} posts`);
  console.log(`  - ${context.postTags.length} unique tags`);
  console.log(`  - ${context.userCategories.length} user categories`);
  console.log(`  - ${context.albumNames.length} album name patterns`);
  
  // Build full system prompt with context
  const systemPrompt = BASE_SYSTEM_PROMPT + '\n\n' + formatContextForPrompt(context);
  
  // Build full user prompt
  const userPrompt = USER_PROMPT_TEMPLATE + OUTPUT_FORMAT_INSTRUCTIONS;

  console.log('\nCalling Claude API...');
  
  const response = await client.messages.create({
    model: 'claude-sonnet-4-20250514',
    max_tokens: 12000,
    messages: [
      { role: 'user', content: userPrompt }
    ],
    system: systemPrompt
  });
  
  // Extract JSON from response
  const responseText = response.content[0].text;
  
  // Try to parse JSON (handle potential markdown code blocks)
  let tasks;
  try {
    const jsonMatch = responseText.match(/\[[\s\S]*\]/);
    if (jsonMatch) {
      tasks = JSON.parse(jsonMatch[0]);
    } else {
      tasks = JSON.parse(responseText);
    }
  } catch (e) {
    console.error('Failed to parse response as JSON:', e);
    console.log('Raw response:', responseText);
    fs.writeFileSync('xhs-raw-response.txt', responseText);
    console.log('Saved raw response to xhs-raw-response.txt for debugging');
    process.exit(1);
  }
  
  // Validate tasks reference valid tags
  const validTags = new Set(context.postTags.map(t => t.tag));
  const validTopics = new Set(context.userCategories.map(c => c.category));
  
  tasks.forEach((t, i) => {
    if (t.topic_area && !validTopics.has(t.topic_area)) {
      // This is just a warning - topic_area might be broader categories
      // console.warn(`⚠️  Task ${i + 1} has topic_area not in user categories: "${t.topic_area}"`);
    }
  });
  
  // Save
  const output = {
    generatedAt: new Date().toISOString(),
    contextUsed: {
      users: context.users.length,
      totalPosts: context.summary.totalPosts,
      uniqueTags: context.postTags.length,
      userCategories: context.userCategories.length,
      albumPatterns: context.albumNames.length
    },
    taskCount: tasks.length,
    tasks
  };
  
  fs.writeFileSync('xhs-generated-tasks.json', JSON.stringify(output, null, 2));
  console.log(`\n✅ Generated ${tasks.length} tasks to xhs-generated-tasks.json`);
  
  // Show summary
  const byWorkflow = {};
  const byTopic = {};
  tasks.forEach(t => {
    byWorkflow[t.workflow] = (byWorkflow[t.workflow] || 0) + 1;
    if (t.topic_area) {
      byTopic[t.topic_area] = (byTopic[t.topic_area] || 0) + 1;
    }
  });
  
  console.log('\nBy workflow:');
  Object.entries(byWorkflow).sort((a, b) => b[1] - a[1]).forEach(([k, v]) => console.log(`  - ${k}: ${v}`));
  
  console.log('\nBy topic area (top 10):');
  Object.entries(byTopic).sort((a, b) => b[1] - a[1]).slice(0, 10).forEach(([k, v]) => console.log(`  - ${k}: ${v}`));
}

generateTasks().catch(console.error);