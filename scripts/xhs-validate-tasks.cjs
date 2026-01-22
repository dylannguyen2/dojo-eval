// scripts/xhs-validate-tasks.js
// Run: node scripts/xhs-validate-tasks.js
// Input: xhs-generated-tasks.json, MongoDB
// Output: xhs-validated-tasks.json

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
    tags: [],
    locations: [],
    collectionNames: [],
    topicAreas: [],
    actions: [],
    contentTypes: []
  };
  
  // Extract @mentions
  const userMentions = prompt.match(/@[\u4e00-\u9fa5\w]+/g) || [];
  mentions.usernames = userMentions.map(u => u.replace('@', ''));
  
  // Extract quoted names (likely collection names or search terms)
  const quotedNames = prompt.match(/["'"'「」]([^"'"'「」]+)["'"'「」]/g) || [];
  mentions.collectionNames = quotedNames.map(n => n.replace(/["'"'「」]/g, ''));
  
  // Extract Chinese location patterns
  const locationPatterns = [
    /在([\u4e00-\u9fa5]{2,8})/g,  // 在北京, 在上海
    /([\u4e00-\u9fa5]{2,4})(旅[游行]|美食|攻略|探店)/g,  // 成都旅游, 北京美食
    /(去|到)([\u4e00-\u9fa5]{2,6})/g  // 去三亚, 到杭州
  ];
  
  for (const pattern of locationPatterns) {
    const matches = [...prompt.matchAll(pattern)];
    for (const match of matches) {
      const location = match[1] || match[2];
      if (location && location.length >= 2) {
        mentions.locations.push(location);
      }
    }
  }
  
  // Topic area keywords (matching XHS content themes)
  const topicKeywords = {
    'fashion': ['fashion', '穿搭', 'outfit', 'style', '时尚', 'ootd', '服装', '衣服', 'dress', '裙子'],
    'beauty': ['beauty', '美妆', 'makeup', 'skincare', '护肤', '化妆', 'cosmetics', '口红', 'lipstick'],
    'food': ['food', '美食', 'recipe', '食谱', 'cooking', '烹饪', 'restaurant', '餐厅', '探店', 'cafe', '咖啡'],
    'travel': ['travel', '旅游', '旅行', 'trip', 'destination', '景点', 'vacation', '度假', 'hotel', '酒店'],
    'fitness': ['fitness', '健身', 'workout', '运动', 'exercise', 'gym', '减肥', 'diet', '瑜伽', 'yoga'],
    'home': ['home', '家居', 'interior', '装修', 'decoration', '收纳', 'organization', '房间', 'room'],
    'pets': ['pets', '宠物', 'cat', '猫', 'dog', '狗', 'puppy', 'kitten'],
    'art': ['art', '艺术', 'painting', '绘画', 'drawing', '画', 'illustration', '插画', 'design', '设计'],
    'tech': ['tech', '科技', 'digital', '数码', 'gadget', 'phone', '手机', 'laptop', '电脑'],
    'lifestyle': ['lifestyle', '生活', 'daily', '日常', 'routine', 'vlog'],
    'parenting': ['parenting', '育儿', 'baby', '宝宝', 'kids', '孩子', 'mother', '妈妈'],
    'education': ['education', '学习', 'study', '考试', 'exam', '英语', 'english'],
    'wedding': ['wedding', '婚礼', 'bride', '新娘', '婚纱', 'marriage'],
    'photography': ['photography', '摄影', 'photo', '拍照', 'camera', '相机']
  };
  
  const promptLower = prompt.toLowerCase();
  for (const [topic, keywords] of Object.entries(topicKeywords)) {
    if (keywords.some(kw => promptLower.includes(kw))) {
      mentions.topicAreas.push(topic);
    }
  }
  
  // Action keywords
  const actionKeywords = {
    'follow': ['follow', '关注', 'subscribe'],
    'unfollow': ['unfollow', '取消关注', '取关'],
    'like': ['like', '点赞', '赞', 'heart'],
    'bookmark': ['bookmark', '收藏', 'save', 'collect'],
    'comment': ['comment', '评论', 'reply', '回复', 'leave a comment'],
    'create_collection': ['create.*collection', '创建.*收藏夹', 'new collection', '新建收藏'],
    'search': ['search', '搜索', 'find', '查找', 'look for'],
    'post': ['post', '发布', 'share', '分享', 'create', '发笔记'],
    'dark_mode': ['dark mode', '深色模式', '夜间模式', 'dark theme'],
    'light_mode': ['light mode', '浅色模式', 'light theme'],
    'notifications': ['notification', '通知', '消息']
  };
  
  for (const [action, patterns] of Object.entries(actionKeywords)) {
    if (patterns.some(p => new RegExp(p, 'i').test(prompt))) {
      mentions.actions.push(action);
    }
  }
  
  // Content type keywords
  if (/video|视频|vlog/i.test(prompt)) {
    mentions.contentTypes.push('video');
  }
  if (/image|photo|图片|照片|picture/i.test(prompt)) {
    mentions.contentTypes.push('image');
  }
  
  return mentions;
}

// ============ Main Validation ============

async function validateTasks() {
  // Load generated tasks
  if (!fs.existsSync('xhs-generated-tasks.json')) {
    console.error('❌ xhs-generated-tasks.json not found. Run xhs-generate-tasks.js first.');
    process.exit(1);
  }
  
  const { tasks } = JSON.parse(fs.readFileSync('xhs-generated-tasks.json', 'utf8'));
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
      postTags,
      postLocations,
      userLocations,
      albums,
      postsByType,
      postsWithComments,
      userCategories
    ] = await Promise.all([
      db.collection('users').find({}, { 
        projection: { displayName: 1, username: 1, category: 1, location: 1 } 
      }).toArray(),
      db.collection('posts').aggregate([
        { $unwind: '$tags' },
        { $group: { _id: '$tags', count: { $sum: 1 } } },
        { $sort: { count: -1 } }
      ]).toArray(),
      db.collection('posts').aggregate([
        { $match: { location: { $exists: true, $ne: null } } },
        { $group: { _id: '$location', count: { $sum: 1 } } }
      ]).toArray(),
      db.collection('users').aggregate([
        { $match: { location: { $exists: true, $ne: null } } },
        { $group: { _id: '$location', count: { $sum: 1 } } }
      ]).toArray(),
      db.collection('users').aggregate([
        { $unwind: '$albums' },
        { $project: { name: '$albums.name', postCount: { $size: '$albums.postIds' } } }
      ]).toArray(),
      db.collection('posts').aggregate([
        { $group: { _id: '$type', count: { $sum: 1 } } }
      ]).toArray(),
      db.collection('posts').countDocuments({ 'comments.0': { $exists: true } }),
      db.collection('users').aggregate([
        { $match: { category: { $exists: true, $ne: null } } },
        { $group: { _id: '$category', count: { $sum: 1 } } }
      ]).toArray()
    ]);
    
    // Build reference sets
    const userDisplayNames = new Set(users.map(u => u.displayName));
    const userDisplayNamesArray = users.map(u => u.displayName);
    const usernames = new Set(users.map(u => u.username));
    const usernamesArray = users.map(u => u.username);
    const allTags = new Set(postTags.map(t => t._id));
    const allTagsArray = postTags.map(t => t._id);
    const allLocations = new Set([
      ...postLocations.map(l => l._id),
      ...userLocations.map(l => l._id)
    ]);
    const allLocationsArray = [...allLocations];
    const albumNames = new Set(albums.map(a => a.name));
    const albumNamesArray = albums.map(a => a.name);
    const categories = new Set(userCategories.map(c => c._id));
    
    const videoPostCount = postsByType.find(p => p._id === 'video')?.count || 0;
    const imagePostCount = postsByType.find(p => p._id === 'image')?.count || 0;
    
    console.log(`Reference data loaded:`);
    console.log(`  - ${users.length} users`);
    console.log(`  - ${allTags.size} unique tags`);
    console.log(`  - ${allLocations.size} locations`);
    console.log(`  - ${albums.length} albums (${albumNames.size} unique names)`);
    console.log(`  - ${videoPostCount} video posts, ${imagePostCount} image posts`);
    console.log(`  - ${postsWithComments} posts with comments`);
    console.log(`  - ${categories.size} user categories\n`);
    
    // Validate each task
    const results = [];
    
    for (let i = 0; i < tasks.length; i++) {
      const task = tasks[i];
      const validation = {
        index: i,
        prompt: task.prompt,
        verification: task.verification,
        workflow: task.workflow,
        topic_area: task.topic_area,
        issues: [],
        warnings: [],
        canFulfill: true
      };
      
      const mentions = extractMentionsFromPrompt(task.prompt);
      
      // Validate user mentions
      for (const username of mentions.usernames) {
        const inDisplayNames = userDisplayNames.has(username);
        const inUsernames = usernames.has(username);
        
        if (!inDisplayNames && !inUsernames) {
          const displayMatch = findBestMatch(username, userDisplayNamesArray);
          const usernameMatch = findBestMatch(username, usernamesArray);
          
          const bestMatch = displayMatch && usernameMatch 
            ? (displayMatch.confidence > usernameMatch.confidence ? displayMatch : usernameMatch)
            : (displayMatch || usernameMatch);
            
          if (bestMatch) {
            validation.warnings.push(
              `User "${username}" not found exactly. Similar: "${bestMatch.value}" (${Math.round(bestMatch.confidence * 100)}% match)`
            );
          } else {
            validation.issues.push(`User "${username}" does not exist in database`);
            validation.canFulfill = false;
          }
        }
      }
      
      // Validate topic/tag mentions
      for (const topic of mentions.topicAreas) {
        // Check if we have posts with related tags
        const relatedTags = allTagsArray.filter(t => 
          t.toLowerCase().includes(topic) || topic.includes(t.toLowerCase())
        );
        
        if (relatedTags.length === 0) {
          validation.warnings.push(
            `Topic "${topic}" may have limited content - no exact tag matches found`
          );
        }
      }
      
      // Validate location mentions
      for (const location of mentions.locations) {
        if (!allLocations.has(location)) {
          const match = findBestMatch(location, allLocationsArray);
          if (match) {
            validation.warnings.push(
              `Location "${location}" not found exactly. Similar: "${match.value}"`
            );
          } else {
            validation.warnings.push(
              `Location "${location}" not found in database - task may not find matching content`
            );
          }
        }
      }
      
      // Validate collection name patterns
      for (const collectionName of mentions.collectionNames) {
        if (mentions.actions.includes('create_collection')) {
          // Creating new collections is fine, check if name pattern is reasonable
          if (collectionName.length > 20) {
            validation.warnings.push(`Collection name "${collectionName}" is quite long`);
          }
        } else if (albumNames.size > 0) {
          // If referencing existing collection
          if (!albumNames.has(collectionName)) {
            const match = findBestMatch(collectionName, albumNamesArray);
            if (match) {
              validation.warnings.push(
                `Collection "${collectionName}" not found. Similar: "${match.value}"`
              );
            }
          }
        }
      }
      
      // Check content type requirements
      if (mentions.contentTypes.includes('video') && videoPostCount === 0) {
        validation.issues.push('Task requires video content but no video posts exist');
        validation.canFulfill = false;
      } else if (mentions.contentTypes.includes('video') && videoPostCount < 5) {
        validation.warnings.push(`Only ${videoPostCount} video posts available`);
      }
      
      if (mentions.contentTypes.includes('image') && imagePostCount === 0) {
        validation.issues.push('Task requires image content but no image posts exist');
        validation.canFulfill = false;
      }
      
      // Check comment-related tasks
      if (mentions.actions.includes('comment')) {
        if (postsWithComments === 0) {
          validation.warnings.push('No posts with existing comments - comment interactions may be limited');
        }
      }
      
      // Check topic area against user categories
      if (task.topic_area) {
        const topicMatchesCategory = [...categories].some(c => 
          c.toLowerCase().includes(task.topic_area.toLowerCase()) ||
          task.topic_area.toLowerCase().includes(c.toLowerCase())
        );
        
        const topicInTags = allTagsArray.some(t =>
          t.toLowerCase().includes(task.topic_area.toLowerCase()) ||
          task.topic_area.toLowerCase().includes(t.toLowerCase())
        );
        
        if (!topicMatchesCategory && !topicInTags) {
          validation.warnings.push(
            `Topic area "${task.topic_area}" may have limited content in database`
          );
        }
      }
      
      // Check for engagement metric requirements
      const engagementPatterns = [
        /(\d+)\s*(likes?|赞)/i,
        /(\d+)\s*(bookmarks?|收藏)/i,
        /(\d+)\s*(comments?|评论)/i,
        /(\d+)\s*(followers?|粉丝)/i,
        /(\d+)\s*(posts?|笔记)/i
      ];
      
      for (const pattern of engagementPatterns) {
        const match = task.prompt.match(pattern);
        if (match) {
          const threshold = parseInt(match[1]);
          if (threshold > 500) {
            validation.warnings.push(
              `Task requires ${threshold}+ ${match[2]} - verify this threshold exists in data`
            );
          }
        }
      }
      
      // Check follow/bookmark capacity
      if (mentions.actions.includes('follow')) {
        if (users.length < 3) {
          validation.warnings.push('Limited users available for follow-related tasks');
        }
      }
      
      if (mentions.actions.includes('bookmark')) {
        const totalPosts = videoPostCount + imagePostCount;
        if (totalPosts < 5) {
          validation.warnings.push(`Only ${totalPosts} posts available for bookmarking`);
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
        r.warnings.slice(0, 3).forEach(w => console.log(`    ⚠️  ${w}`));
        if (r.warnings.length > 3) {
          console.log(`    ... and ${r.warnings.length - 3} more warnings`);
        }
      }
    }
    
    // Analyze by topic area
    const topicCoverage = {};
    for (const task of tasks) {
      if (task.topic_area) {
        topicCoverage[task.topic_area] = (topicCoverage[task.topic_area] || 0) + 1;
      }
    }
    
    console.log(`\n${'─'.repeat(50)}`);
    console.log('TOPIC COVERAGE:');
    console.log('─'.repeat(50));
    Object.entries(topicCoverage)
      .sort((a, b) => b[1] - a[1])
      .forEach(([topic, count]) => console.log(`  ${topic}: ${count} tasks`));
    
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
        uniqueTags: allTags.size,
        locations: allLocations.size,
        albums: albums.length,
        videoPosts: videoPostCount,
        imagePosts: imagePostCount,
        postsWithComments,
        userCategories: categories.size
      },
      topicCoverage,
      validTasks: valid.map(r => ({
        prompt: r.prompt,
        verification: r.verification,
        workflow: r.workflow,
        topic_area: r.topic_area
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
    
    fs.writeFileSync('xhs-validated-tasks.json', JSON.stringify(output, null, 2));
    console.log(`\n✅ Results saved to xhs-validated-tasks.json`);
    
  } finally {
    await client.close();
  }
}

validateTasks().catch(console.error);