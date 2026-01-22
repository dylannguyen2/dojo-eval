// scripts/weibo-validate-tasks.js
// Run: node scripts/weibo-validate-tasks.js
// Input: weibo-generated-tasks.json, MongoDB
// Output: weibo-validated-tasks.json

const { MongoClient } = require('mongodb');
const fs = require('fs');

const MONGO_URI = process.env.MONGO_URI || 'mongodb://localhost:27017';
const DB_NAME = process.env.DB_NAME || 'app';

// ============ Utility Functions ============

function levenshteinDistance(s1, s2) {
  const costs = [];
  for (let i = 0; i <= s1.length; i++) {
    let lastValue = i;
    for (let j = 0; j <= s2.length; j++) {
      if (i === 0) {
        costs[j] = j;
      } else if (j > 0) {
        let newValue = costs[j - 1];
        if (s1.charAt(i - 1) !== s2.charAt(j - 1)) {
          newValue = Math.min(Math.min(newValue, lastValue), costs[j]) + 1;
        }
        costs[j - 1] = lastValue;
        lastValue = newValue;
      }
    }
    if (i > 0) costs[s2.length] = lastValue;
  }
  return costs[s2.length];
}

function similarity(s1, s2) {
  const longer = s1.length > s2.length ? s1 : s2;
  const shorter = s1.length > s2.length ? s2 : s1;
  if (longer.length === 0) return 1.0;
  const editDistance = levenshteinDistance(longer, shorter);
  return (longer.length - editDistance) / longer.length;
}

function findBestMatch(needle, haystack, threshold = 0.6) {
  const needleLower = needle.toLowerCase();
  
  // Exact match
  const exact = haystack.find(h => h.toLowerCase() === needleLower);
  if (exact) return { value: exact, confidence: 1.0 };
  
  // Contains match
  const contains = haystack.find(h => 
    h.toLowerCase().includes(needleLower) || needleLower.includes(h.toLowerCase())
  );
  if (contains) return { value: contains, confidence: 0.85 };
  
  // Fuzzy match
  let bestMatch = null;
  let bestScore = 0;
  
  for (const candidate of haystack) {
    const score = similarity(needleLower, candidate.toLowerCase());
    if (score > bestScore && score > threshold) {
      bestScore = score;
      bestMatch = candidate;
    }
  }
  
  if (bestMatch) return { value: bestMatch, confidence: bestScore };
  return null;
}

function extractMentionsFromPrompt(prompt) {
  const mentions = {
    usernames: [],
    hashtags: [],
    trendingTopics: [],
    contentThemes: [],
    groupNames: [],
    actions: []
  };
  
  // Extract @mentions
  const userMentions = prompt.match(/@[\u4e00-\u9fa5\w]+/g) || [];
  mentions.usernames = userMentions.map(u => u.replace('@', ''));
  
  // Extract #hashtags# (Chinese style with # on both ends)
  const hashtagMatches = prompt.match(/#[\u4e00-\u9fa5\w]+#/g) || [];
  mentions.hashtags = hashtagMatches.map(h => h.replace(/#/g, ''));
  
  // Also extract Western-style hashtags
  const westernHashtags = prompt.match(/#[\u4e00-\u9fa5\w]+(?!\#)/g) || [];
  mentions.hashtags.push(...westernHashtags.map(h => h.replace('#', '')));
  
  // Extract quoted topic/group names
  const quotedNames = prompt.match(/["'"']([^"'"']+)["'"']/g) || [];
  mentions.groupNames = quotedNames.map(n => n.replace(/["'"']/g, ''));
  
  // Content theme keywords
  const themeKeywords = {
    'tech': ['tech', 'technology', '科技', 'ai', 'artificial intelligence', '人工智能', 'digital', 'software', 'coding', 'programming'],
    'entertainment': ['entertainment', '娱乐', 'celebrity', '明星', 'movie', '电影', 'music', '音乐', 'drama', '电视剧', 'variety show', '综艺'],
    'news': ['news', '新闻', 'breaking', '突发', 'current events', '时事', 'politics', '政治'],
    'sports': ['sports', '体育', 'football', '足球', 'basketball', '篮球', 'olympics', '奥运', 'athlete', '运动员'],
    'food': ['food', '美食', 'restaurant', '餐厅', 'cooking', '烹饪', 'recipe', '食谱', 'delicious', '好吃'],
    'travel': ['travel', '旅游', 'trip', '旅行', 'destination', '目的地', 'vacation', '度假', 'scenery', '风景'],
    'fashion': ['fashion', '时尚', 'style', '穿搭', 'outfit', 'clothing', '服装', 'beauty', '美妆'],
    'humor': ['humor', 'funny', '搞笑', 'meme', '段子', 'joke', '笑话', 'comedy', '喜剧'],
    'finance': ['finance', '财经', 'stock', '股票', 'investment', '投资', 'economy', '经济', 'crypto', '加密货币'],
    'gaming': ['gaming', 'game', '游戏', 'esports', '电竞', 'player', '玩家'],
    'health': ['health', '健康', 'fitness', '健身', 'workout', '锻炼', 'diet', '饮食'],
    'education': ['education', '教育', 'learning', '学习', 'study', '考试', 'university', '大学'],
    'lifestyle': ['lifestyle', '生活', 'daily', '日常', 'routine', '生活方式']
  };
  
  const promptLower = prompt.toLowerCase();
  for (const [theme, keywords] of Object.entries(themeKeywords)) {
    if (keywords.some(kw => promptLower.includes(kw))) {
      mentions.contentThemes.push(theme);
    }
  }
  
  // Action keywords
  const actionKeywords = {
    'follow': ['follow', '关注', 'subscribe'],
    'unfollow': ['unfollow', '取消关注', '取关'],
    'like': ['like', '点赞', '赞'],
    'comment': ['comment', '评论', 'reply', '回复'],
    'repost': ['repost', '转发', 'share', '分享'],
    'create_group': ['create.*group', '创建.*分组', 'new group', '新建分组'],
    'special_attention': ['special attention', '特别关注', 'priority'],
    'post': ['post', '发布', 'compose', '发微博', 'write', '写'],
    'search': ['search', '搜索', 'find', '查找'],
    'trending': ['trending', '热搜', 'hot topic', '热门']
  };
  
  for (const [action, patterns] of Object.entries(actionKeywords)) {
    if (patterns.some(p => new RegExp(p, 'i').test(prompt))) {
      mentions.actions.push(action);
    }
  }
  
  return mentions;
}

// ============ Main Validation ============

async function validateTasks() {
  // Load generated tasks
  if (!fs.existsSync('weibo-generated-tasks.json')) {
    console.error('❌ weibo-generated-tasks.json not found. Run weibo-generate-tasks.js first.');
    process.exit(1);
  }
  
  const { tasks } = JSON.parse(fs.readFileSync('weibo-generated-tasks.json', 'utf8'));
  console.log(`Loaded ${tasks.length} tasks to validate`);
  
  const client = new MongoClient(MONGO_URI);
  
  try {
    await client.connect();
    console.log('Connected to MongoDB\n');
    
    const db = client.db(DB_NAME);
    
    // Load reference data
    console.log('Loading reference data...');
    const [
      users,
      trendingTopics,
      hashtagTopics,
      postHashtags,
      customGroups,
      postsWithComments,
      verifiedUsers
    ] = await Promise.all([
      db.collection('users').find({}, { projection: { name: 1, verified: 1, verifiedTitle: 1, bio: 1 } }).toArray(),
      db.collection('trendingTopics').find({}, { projection: { text: 1, isHashtag: 1 } }).toArray(),
      db.collection('hashtagTopics').find({}, { projection: { text: 1, categories: 1 } }).toArray(),
      db.collection('posts').aggregate([
        { $unwind: '$hashtags' },
        { $group: { _id: '$hashtags.text' } }
      ]).toArray(),
      db.collection('customGroups').find({}, { projection: { label: 1 } }).toArray(),
      db.collection('posts').countDocuments({ 'comments.0': { $exists: true } }),
      db.collection('users').find({ verified: true }, { projection: { name: 1, verifiedTitle: 1 } }).toArray()
    ]);
    
    // Build reference sets
    const userNames = new Set(users.map(u => u.name));
    const userNamesArray = users.map(u => u.name);
    const trendingTexts = new Set(trendingTopics.map(t => t.text));
    const trendingTextsArray = trendingTopics.map(t => t.text);
    const allHashtags = new Set([
      ...hashtagTopics.map(h => h.text),
      ...postHashtags.map(h => h._id)
    ]);
    const allHashtagsArray = [...allHashtags];
    const existingGroups = new Set(customGroups.map(g => g.label));
    const hashtagCategories = new Set(hashtagTopics.flatMap(h => h.categories || []));
    
    console.log(`Reference data loaded:`);
    console.log(`  - ${users.length} users (${verifiedUsers.length} verified)`);
    console.log(`  - ${trendingTopics.length} trending topics`);
    console.log(`  - ${allHashtags.size} unique hashtags`);
    console.log(`  - ${customGroups.length} existing custom groups`);
    console.log(`  - ${postsWithComments} posts with comments\n`);
    
    // Validate each task
    const results = [];
    
    for (let i = 0; i < tasks.length; i++) {
      const task = tasks[i];
      const validation = {
        index: i,
        prompt: task.prompt,
        verification: task.verification,
        workflow: task.workflow,
        content_theme: task.content_theme,
        issues: [],
        warnings: [],
        canFulfill: true
      };
      
      const mentions = extractMentionsFromPrompt(task.prompt);
      
      // Validate user mentions
      for (const username of mentions.usernames) {
        if (!userNames.has(username)) {
          const match = findBestMatch(username, userNamesArray);
          if (match) {
            validation.warnings.push(
              `User "@${username}" not found exactly. Did you mean "@${match.value}"? (${Math.round(match.confidence * 100)}% match)`
            );
          } else {
            validation.issues.push(`User "@${username}" does not exist in database`);
            validation.canFulfill = false;
          }
        }
      }
      
      // Validate hashtag mentions
      for (const hashtag of mentions.hashtags) {
        if (!allHashtags.has(hashtag)) {
          const match = findBestMatch(hashtag, allHashtagsArray);
          if (match) {
            validation.warnings.push(
              `Hashtag "#${hashtag}#" not found exactly. Similar: "#${match.value}#" (${Math.round(match.confidence * 100)}% match)`
            );
          } else {
            validation.warnings.push(`Hashtag "#${hashtag}#" not found in database (may be created dynamically)`);
          }
        }
      }
      
      // Check if trending topics mentioned exist
      if (mentions.actions.includes('trending')) {
        // Task involves trending topics - check if we have enough
        if (trendingTopics.length === 0) {
          validation.issues.push('Task requires trending topics but none exist in database');
          validation.canFulfill = false;
        }
      }
      
      // Validate content theme against available content
      if (task.content_theme) {
        const themeMatchesHashtagCategory = hashtagCategories.has(task.content_theme);
        const themeInUserBios = users.some(u => 
          u.bio && u.bio.toLowerCase().includes(task.content_theme.toLowerCase())
        );
        
        if (!themeMatchesHashtagCategory && !themeInUserBios) {
          validation.warnings.push(
            `Content theme "${task.content_theme}" may have limited content in database`
          );
        }
      }
      
      // Check for comment-related tasks
      if (mentions.actions.includes('comment')) {
        if (postsWithComments === 0) {
          validation.issues.push('Task requires commenting but no posts with comments exist');
          validation.canFulfill = false;
        }
      }
      
      // Check for follow/special attention tasks
      if (mentions.actions.includes('follow') || mentions.actions.includes('special_attention')) {
        if (users.length < 3) {
          validation.warnings.push('Limited users available for follow-related tasks');
        }
      }
      
      // Check if tasks reference verified users specifically
      if (task.prompt.toLowerCase().includes('verified') || task.prompt.includes('认证')) {
        if (verifiedUsers.length === 0) {
          validation.issues.push('Task requires verified users but none exist');
          validation.canFulfill = false;
        } else if (verifiedUsers.length < 3) {
          validation.warnings.push(`Only ${verifiedUsers.length} verified users available`);
        }
      }
      
      // Check for group-related tasks with specific names
      for (const groupName of mentions.groupNames) {
        if (mentions.actions.includes('create_group')) {
          // Creating new groups is fine
          continue;
        }
        // If referencing existing group, check if similar exists
        if (existingGroups.size > 0 && !existingGroups.has(groupName)) {
          const match = findBestMatch(groupName, [...existingGroups]);
          if (match) {
            validation.warnings.push(
              `Group "${groupName}" not found. Similar: "${match.value}"`
            );
          }
        }
      }
      
      // Check for engagement metrics requirements
      const engagementPatterns = [
        /(\d+)\s*(likes?|赞)/i,
        /(\d+)\s*(comments?|评论)/i,
        /(\d+)\s*(reposts?|转发)/i,
        /(\d+)\s*(followers?|粉丝)/i
      ];
      
      for (const pattern of engagementPatterns) {
        const match = task.prompt.match(pattern);
        if (match) {
          const threshold = parseInt(match[1]);
          if (threshold > 1000) {
            validation.warnings.push(
              `Task requires ${threshold}+ ${match[2]} - verify this threshold exists in data`
            );
          }
        }
      }
      
      results.push(validation);
      
      // Progress indicator
      if ((i + 1) % 10 === 0) {
        console.log(`Validated ${i + 1}/${tasks.length} tasks...`);
      }
    }
    
    // Summary
    const valid = results.filter(r => r.canFulfill && r.issues.length === 0);
    const withWarnings = results.filter(r => r.canFulfill && r.warnings.length > 0);
    const invalid = results.filter(r => !r.canFulfill);
    
    console.log(`\n${'='.repeat(50)}`);
    console.log('VALIDATION SUMMARY');
    console.log('='.repeat(50));
    console.log(`✅ Valid:         ${valid.length}`);
    console.log(`⚠️  With warnings: ${withWarnings.length}`);
    console.log(`❌ Invalid:       ${invalid.length}`);
    
    if (invalid.length > 0) {
      console.log(`\n${'─'.repeat(50)}`);
      console.log('INVALID TASKS:');
      console.log('─'.repeat(50));
      for (const r of invalid) {
        console.log(`\n[${r.index}] "${r.prompt.substring(0, 70)}..."`);
        r.issues.forEach(i => console.log(`    ❌ ${i}`));
      }
    }
    
    if (withWarnings.length > 0) {
      console.log(`\n${'─'.repeat(50)}`);
      console.log('TASKS WITH WARNINGS (first 10):');
      console.log('─'.repeat(50));
      for (const r of withWarnings.slice(0, 10)) {
        console.log(`\n[${r.index}] "${r.prompt.substring(0, 60)}..."`);
        r.warnings.forEach(w => console.log(`    ⚠️  ${w}`));
      }
    }
    
    // Save results
    const output = {
      validatedAt: new Date().toISOString(),
      summary: {
        total: results.length,
        valid: valid.length,
        withWarnings: withWarnings.length,
        invalid: invalid.length
      },
      referenceData: {
        users: users.length,
        verifiedUsers: verifiedUsers.length,
        trendingTopics: trendingTopics.length,
        hashtags: allHashtags.size,
        customGroups: customGroups.length
      },
      validTasks: valid.map(r => ({
        prompt: r.prompt,
        verification: r.verification,
        workflow: r.workflow,
        content_theme: r.content_theme
      })),
      invalidTasks: invalid.map(r => ({
        prompt: r.prompt,
        verification: r.verification,
        issues: r.issues
      })),
      tasksWithWarnings: withWarnings.map(r => ({
        prompt: r.prompt,
        verification: r.verification,
        warnings: r.warnings
      }))
    };
    
    fs.writeFileSync('weibo-validated-tasks.json', JSON.stringify(output, null, 2));
    console.log(`\n✅ Results saved to weibo-validated-tasks.json`);
    
  } finally {
    await client.close();
  }
}

validateTasks().catch(console.error);