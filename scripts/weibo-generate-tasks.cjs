// scripts/weibo-generate-tasks.js
// Run: node scripts/weibo-generate-tasks.js
// Input: weibo-db-context.json
// Output: weibo-generated-tasks.json

const Anthropic = require('@anthropic-ai/sdk');
const fs = require('fs');

const client = new Anthropic();

function formatContextForPrompt(ctx) {
  return `
## Available Data in Mock Weibo Environment

**Trending Topics (${ctx.trendingTopics.length} total):**
${ctx.trendingTopics.slice(0, 25).map(t => {
  const labels = [t.label, t.isPinned ? '置顶' : null, t.isHashtag ? 'hashtag' : null].filter(Boolean).join(', ');
  return `- "${t.text}" ${t.count ? `(${t.count})` : ''} ${labels ? `[${labels}]` : ''}`;
}).join('\n')}

**Hashtag Topics with Categories:**
${ctx.hashtagTopics.slice(0, 20).map(h => `- #${h.text}# (${h.readCount} reads, ${h.discussionCount} discussions) — Categories: ${h.categories.join(', ')}`).join('\n')}

**Hashtag Categories:**
${ctx.hashtagCategories.slice(0, 15).map(c => `- ${c.category} (${c.count} topics)`).join('\n')}

**Hashtags found in posts:**
${ctx.postHashtags.slice(0, 30).map(h => `- #${h.hashtag}# (${h.count} posts)`).join('\n')}

**Users (${ctx.users.length} total):**
${ctx.users.slice(0, 25).map(u => {
  const verified = u.verified ? `✓ ${u.verifiedTitle || u.verifiedType || 'verified'}` : '';
  const stats = [u.followersCount ? `${u.followersCount} followers` : null, u.postsCount ? `${u.postsCount} posts` : null].filter(Boolean).join(', ');
  return `- "${u.name}" ${verified} ${u.location ? `(${u.location})` : ''} — ${stats || 'no stats'} — Bio: ${(u.bio || 'no bio').substring(0, 50)}`;
}).join('\n')}

**Verified Users:**
${ctx.verifiedUsers.slice(0, 15).map(u => `- "${u.name}" (${u.verifiedTitle || u.verifiedType || 'verified'}) — ${(u.bio || '').substring(0, 40)}`).join('\n')}

**Suggested Users:**
${ctx.suggestedUsers.slice(0, 15).map(u => `- "${u.name}" ${u.verified ? '✓' : ''} — ${u.description.substring(0, 50)}`).join('\n')}

**User Locations:**
${ctx.userLocations.slice(0, 15).map(l => `- ${l.location} (${l.count} users)`).join('\n')}

**Existing Custom Groups:**
${ctx.customGroups.length > 0 ? ctx.customGroups.map(g => `- "${g}"`).join('\n') : '- (none currently exist)'}

**Sample Posts with Hashtags:**
${ctx.postsWithHashtags.slice(0, 15).map(p => `- @${p.userName}: "${p.content}..." — Hashtags: ${(p.hashtags || []).map(h => `#${h}#`).join(', ')} (${p.likeCount} likes)`).join('\n')}

**High Engagement Posts:**
${ctx.highEngagementPosts.slice(0, 15).map(p => `- @${p.userName}: "${p.content}..." (${p.likeCount} likes, ${p.commentsCount || 0} comments) — Hashtags: ${(p.hashtags || []).map(h => `#${h}#`).join(', ') || 'none'}`).join('\n')}

**Posts with Media:**
${ctx.postsWithMedia.slice(0, 10).map(p => `- @${p.userName}: "${p.content}..." — Has images: ${p.hasImages}, Media types: ${(p.mediaTypes || []).join(', ') || 'N/A'}`).join('\n')}

**Sample Comments:**
${ctx.sampleComments.slice(0, 10).map(c => `- @${c.userName}: "${c.content}" (${c.likes || 0} likes, ${c.repliesCount || 0} replies)`).join('\n')}

---
⚠️ CRITICAL CONSTRAINTS:
1. ONLY reference users that exist in the users list above
2. ONLY reference trending topics and hashtags from the lists above
3. When creating custom groups, use realistic Chinese names
4. Hashtag format is #话题# (with # on both sides)
5. User content themes should match what's visible in their posts/bio
6. For tasks involving specific users, USE the user names listed above
7. Do NOT invent users, trending topics, or hashtags that aren't in this data
`;
}

// ============================================================
// PASTE YOUR SYSTEM PROMPT BELOW (between the backticks)
// This is the base system prompt - context will be appended
// ============================================================
const BASE_SYSTEM_PROMPT = `# Task: Generate User Prompts for Weibo Agent Evaluation

## App Capabilities

---BEGIN CAPABILITIES---
## Environment Overview

**Target Website:** Weibo

**Environment Type:** Fully mocked, programmable web application

**Key Characteristics:**

- High-value Chinese social media platform
- Real-time content feed with infinite scroll
- Complex social graph interactions (follow, groups, attention levels)
- Rich multimedia posts with comments and engagement
- Trending topics and search functionality

---

## Core Workflows

### Workflow 1: Content Discovery & Navigation

**User Goal:** Discover and consume social media content through feeds, search, and trending topics

**Key Interactions:**

1. **Homepage Feed Exploration**
    - 🟩 View main feed with posts from followed users
    - 🟩 Infinite scroll to load additional posts
    - 🟩 Navigate between feed sections:
        - Main feed
        - Special Attention
        - Latest Weibo
        - Custom Groups
    - 🟩 View post content (text, images, videos)
    - 🟩 Click on profile pictures to view user profiles
    - 🟩 Click on timestamps to view detailed post pages
2. **Search Functionality**
    - 🟩 Enter search queries in main search box
    - 🟩 View user profile suggestions in dropdown
    - 🟩 Click profiles in dropdown to navigate to profile pages
    - 🟩 Access user icon to see relevant profile results
    - 🟩 Navigate to profile pages from search results
3. **Trending Topics Navigation**
    - 🟩 View trending topics in sidebar
    - 🟩 Click trending topics to view related posts
    - 🟩 Navigate to topic-specific search pages
    - 🟩 Browse posts tagged with specific topics
    - 🟩 Custom page headers for trending topics

**Success Criteria:**

- 🟩 Agent can navigate between different feed sections seamlessly
- 🟩 Infinite scroll loads content smoothly
- 🟩 Search functionality returns relevant profiles
- 🟩 Trending topics lead to appropriate content
- 🟩 All navigation maintains application state

---

### Workflow 2: Social Graph Management

**User Goal:** Build and manage social connections through following, grouping, and organizing users

**Key Interactions:**

1. **Follow/Unfollow Actions**
    - 🟩 Follow users from profile pages
    - 🟩 Unfollow users from profile pages
    - 🟩 View followed users in different feed sections
    - 🟩 Follow users discovered through search
    - 🟩 Follow users from post interactions
2. **Attention Level Management**
    - 🟩 Assign users to \"Special Attention\" category
    - 🟩 View Special Attention feed with prioritized content
    - 🟩 Remove users from Special Attention
    - 🟩 Manage attention levels for different users
3. **Custom Group Management**
    - 🟩 Create new custom groups
    - 🟩 Delete existing custom groups
    - 🟩 Assign followed users to custom groups
    - 🟩 Remove users from custom groups
    - 🟩 View custom group-specific feeds
    - 🟩 Navigate between multiple custom groups
    - 🟩 Organize social connections by interest/category

**Success Criteria:**

- 🟩 Follow/unfollow actions update feeds correctly
- 🟩 Special Attention assignments affect feed visibility
- 🟩 Custom groups can be created, modified, and deleted
- 🟩 Posts appear in correct feed sections based on user assignments
- 🟩 Group assignments persist across sessions

---

### Workflow 3: Content Engagement & Creation

**User Goal:** Engage with existing content and create new posts

**Key Interactions:**

1. **Post Engagement**
    - 🟩 Like posts from feed or detailed view
    - 🟩 Unlike previously liked posts
    - 🟩 Comment on posts
    - 🟩 View existing comments on posts
    - 🟩 Like comments
    - 🟩 Reply to comments
    - 🟩 View comment threads
    - 🟩 Navigate to commenter profiles
2. **Content Creation**
    - 🟩 Create new posts from homepage
    - 🟩 Compose text content
    - 🟩 Use emoji picker/dropdown
    - 🟩 Add hashtags and mentions
    - 🟩 Publish posts
    - 🟩 View own posts in feed
3. **Profile Interaction**
    - 🟩 View user profiles from various entry points
    - 🟩 Browse user's post history
    - 🟩 View user follower/following counts
    - 🟩 Access user profile information
    - 🟩 Navigate back to feed from profiles

**Success Criteria:**

- 🟩 Like/unlike actions update immediately
- 🟩 Comments post successfully and appear in threads
- 🟩 New posts appear in appropriate feeds
- 🟩 Emoji picker functions correctly
- 🟩 Profile pages display user content accurately
- 🟩 Engagement actions persist across navigation

---END CAPABILITIES---

## Verifiable End States
The agent's success can ONLY be verified via a final snapshot of the app. Valid verifiable states:

- **Following**: User is following specific accounts (visible on profile or following list)
- **Special Attention**: Specific users are assigned to Special Attention category (visible in Special Attention feed)
- **Custom Groups**: A group with a specific name exists; specific users are assigned to groups
- **Posts created**: A new post exists with specific content/hashtags (visible in user's profile or feed)
- **Comments**: A comment with specific text exists on a post
- **Likes**: Posts or comments show as liked by user
- **Current screen**: User is on a specific page (profile, trending topic, custom group feed, search results, etc.)
- **Feed section**: User is viewing a specific feed tab (Main, Special Attention, Latest, or custom group)

**NOT verifiable (avoid prompts that rely solely on these):**
- Navigation history or pages scrolled through
- Posts read but not engaged with
- Search queries attempted (unless results currently displayed)
- Agent's internal observations or summaries
- Transient UI states like dropdown menus`
// ============================================================

// ============================================================
// PASTE YOUR USER PROMPT BELOW (between the backticks)
// ============================================================
const USER_PROMPT_TEMPLATE = `Generate 50 task prompts for a computer-use agent operating Weibo (Chinese social media platform).

## Style Requirements

**Voice & Tone:**
- Sound like a real person casually asking an assistant for help managing their social media
- Vary sentence structure—don't always start with \"I\"
- Use natural quantities (\"a few\", \"some accounts\", \"a couple\") not exact numbers

**Structure:**
- Embed rich context that establishes a real social media situation or motivation
- Include preference constraints that feel human (\"not spam accounts\", \"actually posts regularly\", \"someone chill not drama\")
- Combine multiple related actions naturally (e.g., follow accounts AND organize into group, find trending topic AND engage with posts)
- Express the desired outcome as a goal, not a procedure

**Complexity:**
- Each prompt should involve 2-3 verifiable actions
- Cover different workflows: feed navigation, social graph management, content engagement, content creation
- Vary the specificity—some prompts very targeted, others more open-ended

## Output Format

For each prompt, provide:
1. The natural language prompt
2. Verification criteria in parentheses with concrete, measurable outcomes

## Examples

Prompt: \"I keep missing updates from my favorite tech bloggers because the algorithm buries them. Find a couple of tech accounts I'm following and add them to Special Attention so I actually see their posts.\"
Verification: (≥2 tech-related accounts are in Special Attention category; accounts were already followed)

Prompt: \"Want to organize my feed better—create a group for food and restaurant content, then add some food bloggers I follow to it so I can browse food posts separately.\"
Verification: (Custom group exists with food-related name; ≥2 food/restaurant accounts assigned to the group)

Prompt: \"There's probably something trending about the new iPhone launch. Find the trending topic and leave a comment sharing my thoughts on one of the discussion posts.\"
Verification: (Current screen shows iPhone/Apple-related trending topic or search; comment exists on a post within that topic)

Prompt: \"Been meaning to post something about my weekend hiking trip. Write a post about enjoying nature with some relevant hashtags, nothing too long.\"
Verification: (New post exists on user's profile containing hiking/nature content and ≥1 hashtag)

Prompt: \"My feed is so cluttered with random stuff. Set me up with a group just for close friends—call it something like '好友' or whatever—so I have a quieter feed to check.\"
Verification: (Custom group exists named \"好友\" or similar friends-related name)

Prompt: \"Saw some funny posts earlier today and forgot to like them. Go find some humor or meme content in the feed and like a few posts that are actually funny, not just random stuff.\"
Verification: (≥2 humor/meme-related posts show as liked)

---

Now generate 50 prompts. Ensure prompts are in english (can use chinese terminology if necessary) and have variety across:
- Workflows (feed navigation, social graph/groups, engagement, content creation)
- Action combinations (follow+organize, browse trending+engage, create post+add hashtags, manage groups+assign users)
- Content contexts (tech, entertainment, news, lifestyle, sports, humor, food, travel, etc.)
- User motivations (organizing feeds, engaging with community, following trends, curating experience, posting updates)`;

// ============================================================

// Additional instructions appended to user prompt for JSON output
const OUTPUT_FORMAT_INSTRUCTIONS = `

## Output Format

Return a JSON array where each element has:
- "prompt": the natural language task prompt
- "verification": concrete, measurable success criteria
- "workflow": one of "feed_navigation", "social_graph", "content_engagement", "content_creation"
- "content_theme": the primary content theme (e.g., "tech", "entertainment", "food", "travel", etc.)

Return ONLY the JSON array, no other text.`;

async function generateTasks() {
  // Load context
  if (!fs.existsSync('weibo-db-context.json')) {
    console.error('❌ weibo-db-context.json not found. Run weibo-extract-context.js first.');
    process.exit(1);
  }
  
  const context = JSON.parse(fs.readFileSync('weibo-db-context.json', 'utf8'));
  console.log('Loaded context from weibo-db-context.json');
  console.log(`  - ${context.users.length} users (${context.verifiedUsers.length} verified)`);
  console.log(`  - ${context.trendingTopics.length} trending topics`);
  console.log(`  - ${context.hashtagTopics.length} hashtag topics`);
  console.log(`  - ${context.postHashtags.length} hashtags in posts`);
  console.log(`  - ${context.customGroups.length} custom groups`);
  
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
    fs.writeFileSync('weibo-raw-response.txt', responseText);
    console.log('Saved raw response to weibo-raw-response.txt for debugging');
    process.exit(1);
  }
  
  // Validate tasks reference valid users
  const validUserNames = new Set(context.users.map(u => u.name));
  const validHashtags = new Set([
    ...context.postHashtags.map(h => h.hashtag),
    ...context.hashtagTopics.map(h => h.text),
    ...context.trendingTopics.filter(t => t.isHashtag).map(t => t.text)
  ]);
  
  tasks.forEach((t, i) => {
    // Check if task mentions specific users that don't exist
    const mentionedUsers = t.prompt.match(/@[\u4e00-\u9fa5\w]+/g) || [];
    mentionedUsers.forEach(u => {
      const name = u.replace('@', '');
      if (!validUserNames.has(name)) {
        console.warn(`⚠️  Task ${i + 1} mentions unknown user: "${name}"`);
      }
    });
  });
  
  // Save
  const output = {
    generatedAt: new Date().toISOString(),
    contextUsed: {
      users: context.users.length,
      verifiedUsers: context.verifiedUsers.length,
      trendingTopics: context.trendingTopics.length,
      hashtagTopics: context.hashtagTopics.length,
      customGroups: context.customGroups.length
    },
    taskCount: tasks.length,
    tasks
  };
  
  fs.writeFileSync('weibo-generated-tasks.json', JSON.stringify(output, null, 2));
  console.log(`\n✅ Generated ${tasks.length} tasks to weibo-generated-tasks.json`);
  
  // Show summary
  const byWorkflow = {};
  const byTheme = {};
  tasks.forEach(t => {
    byWorkflow[t.workflow] = (byWorkflow[t.workflow] || 0) + 1;
    if (t.content_theme) {
      byTheme[t.content_theme] = (byTheme[t.content_theme] || 0) + 1;
    }
  });
  
  console.log('\nBy workflow:');
  Object.entries(byWorkflow).sort((a, b) => b[1] - a[1]).forEach(([k, v]) => console.log(`  - ${k}: ${v}`));
  
  console.log('\nBy content theme (top 10):');
  Object.entries(byTheme).sort((a, b) => b[1] - a[1]).slice(0, 10).forEach(([k, v]) => console.log(`  - ${k}: ${v}`));
}

generateTasks().catch(console.error);