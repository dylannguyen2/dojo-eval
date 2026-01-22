// scripts/weibo-extract-context.js
// Run: node scripts/weibo-extract-context.js
// Output: weibo-db-context.json

const { MongoClient } = require('mongodb');
const fs = require('fs');

const MONGO_URI = process.env.MONGO_URI || 'mongodb://localhost:27017';
const DB_NAME = process.env.DB_NAME || 'app';

async function extractContext() {
  const client = new MongoClient(MONGO_URI);
  
  try {
    await client.connect();
    console.log('Connected to MongoDB');
    
    const db = client.db(DB_NAME);
    
    // 1. Get all trending topics
    console.log('Extracting trending topics...');
    const trendingTopics = await db.collection('trendingTopics').find({}, {
      projection: { text: 1, count: 1, label: 1, isPinned: 1, isHashtag: 1, rank: 1 }
    }).sort({ rank: 1 }).toArray();
    
    // 2. Get hashtag topics with categories
    console.log('Extracting hashtag topics...');
    const hashtagTopics = await db.collection('hashtagTopics').find({}, {
      projection: { 
        text: 1, 
        categories: 1, 
        readCount: 1, 
        discussionCount: 1,
        introduction: 1
      }
    }).toArray();
    
    // 3. Get unique hashtag categories
    console.log('Extracting hashtag categories...');
    const hashtagCategories = await db.collection('hashtagTopics').aggregate([
      { $unwind: '$categories' },
      { $group: { _id: '$categories', count: { $sum: 1 } } },
      { $sort: { count: -1 } }
    ]).toArray();
    
    // 4. Get all users with their details
    console.log('Extracting users...');
    const users = await db.collection('users').find({}, {
      projection: { 
        name: 1, 
        bio: 1, 
        verified: 1, 
        verifiedType: 1,
        verifiedTitle: 1,
        followersCount: 1,
        followingCount: 1,
        postsCount: 1,
        location: 1
      }
    }).toArray();
    
    // 5. Get verified users
    console.log('Extracting verified users...');
    const verifiedUsers = await db.collection('users').find(
      { verified: true },
      { projection: { name: 1, verifiedTitle: 1, verifiedType: 1, bio: 1 } }
    ).toArray();
    
    // 6. Get suggested users
    console.log('Extracting suggested users...');
    const suggestedUsers = await db.collection('suggestedUsers').find({}, {
      projection: { name: 1, description: 1, verified: 1 }
    }).toArray();
    
    // 7. Sample posts with hashtags
    console.log('Extracting posts with hashtags...');
    const postsWithHashtags = await db.collection('posts').aggregate([
      { $match: { 'hashtags.0': { $exists: true } } },
      { $sample: { size: 25 } },
      { $project: {
        content: { $substrCP: ['$content', 0, 100] },
        hashtags: '$hashtags.text',
        likeCount: 1,
        commentsCount: 1,
        userName: '$user.name'
      }}
    ]).toArray();
    
    // 8. Get all unique hashtags from posts
    console.log('Extracting unique hashtags from posts...');
    const postHashtags = await db.collection('posts').aggregate([
      { $unwind: '$hashtags' },
      { $group: { 
        _id: '$hashtags.text',
        count: { $sum: 1 }
      }},
      { $sort: { count: -1 } },
      { $limit: 50 }
    ]).toArray();
    
    // 9. Sample posts with high engagement
    console.log('Extracting high engagement posts...');
    const highEngagementPosts = await db.collection('posts').aggregate([
      { $match: { likeCount: { $gt: 100 } } },
      { $sort: { likeCount: -1 } },
      { $limit: 20 },
      { $project: {
        content: { $substrCP: ['$content', 0, 150] },
        likeCount: 1,
        commentsCount: 1,
        repostCount: 1,
        userName: '$user.name',
        hashtags: '$hashtags.text'
      }}
    ]).toArray();
    
    // 10. Posts with images/videos
    console.log('Extracting posts with media...');
    const postsWithMedia = await db.collection('posts').aggregate([
      { $match: { $or: [
        { 'images.0': { $exists: true } },
        { 'media.0': { $exists: true } }
      ]}},
      { $sample: { size: 15 } },
      { $project: {
        content: { $substrCP: ['$content', 0, 100] },
        hasImages: { $cond: [{ $gt: [{ $size: { $ifNull: ['$images', []] } }, 0] }, true, false] },
        mediaTypes: '$media.type',
        userName: '$user.name'
      }}
    ]).toArray();
    
    // 11. Sample comments
    console.log('Extracting sample comments...');
    const sampleComments = await db.collection('comments').aggregate([
      { $sample: { size: 20 } },
      { $project: {
        content: 1,
        likes: 1,
        userName: '$user.name',
        repliesCount: 1
      }}
    ]).toArray();
    
    // 12. Existing custom groups
    console.log('Extracting custom groups...');
    const customGroups = await db.collection('customGroups').find({}, {
      projection: { label: 1 }
    }).toArray();
    
    // 13. User follows (sample)
    console.log('Extracting user follows...');
    const userFollows = await db.collection('userFollows').find({}).limit(50).toArray();
    
    // 14. User likes (sample)
    console.log('Extracting user likes...');
    const userLikes = await db.collection('userLikes').find({}).limit(50).toArray();
    
    // 15. Users by location
    console.log('Extracting user locations...');
    const userLocations = await db.collection('users').aggregate([
      { $match: { location: { $exists: true, $ne: null } } },
      { $group: { _id: '$location', count: { $sum: 1 } } },
      { $sort: { count: -1 } },
      { $limit: 20 }
    ]).toArray();
    
    // 16. Content themes analysis (based on post content keywords)
    console.log('Analyzing content themes...');
    const allPosts = await db.collection('posts').find({}, {
      projection: { content: 1, hashtags: 1 }
    }).toArray();
    
    const context = {
      extractedAt: new Date().toISOString(),
      summary: {
        totalUsers: users.length,
        totalVerifiedUsers: verifiedUsers.length,
        totalTrendingTopics: trendingTopics.length,
        totalHashtagTopics: hashtagTopics.length,
        totalPosts: allPosts.length,
        totalCustomGroups: customGroups.length
      },
      trendingTopics,
      hashtagTopics,
      hashtagCategories: hashtagCategories.map(c => ({ category: c._id, count: c.count })),
      postHashtags: postHashtags.map(h => ({ hashtag: h._id, count: h.count })),
      users,
      verifiedUsers,
      suggestedUsers,
      userLocations: userLocations.map(l => ({ location: l._id, count: l.count })),
      customGroups: customGroups.map(g => g.label),
      postsWithHashtags,
      highEngagementPosts,
      postsWithMedia,
      sampleComments,
      userFollowsSample: userFollows,
      userLikesSample: userLikes
    };
    
    // Write to file
    fs.writeFileSync('weibo-db-context.json', JSON.stringify(context, null, 2));
    console.log('\n✅ Context extracted to weibo-db-context.json');
    console.log(`   - ${users.length} users (${verifiedUsers.length} verified)`);
    console.log(`   - ${trendingTopics.length} trending topics`);
    console.log(`   - ${hashtagTopics.length} hashtag topics`);
    console.log(`   - ${hashtagCategories.length} hashtag categories`);
    console.log(`   - ${postHashtags.length} unique hashtags in posts`);
    console.log(`   - ${customGroups.length} custom groups`);
    console.log(`   - ${suggestedUsers.length} suggested users`);
    
  } finally {
    await client.close();
  }
}

extractContext().catch(console.error);