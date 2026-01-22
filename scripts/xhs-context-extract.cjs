// scripts/xhs-extract-context.js
// Run: node scripts/xhs-extract-context.js
// Output: xhs-db-context.json

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
    
    // 1. Get all users with their categories
    console.log('Extracting users...');
    const users = await db.collection('users').find({}, {
      projection: { 
        displayName: 1, 
        username: 1,
        bio: 1, 
        category: 1,
        location: 1,
        gender: 1,
        likeCount: 1,
        bookmarkedCount: 1
      }
    }).toArray();
    
    // 2. Get unique user categories
    console.log('Extracting user categories...');
    const userCategories = await db.collection('users').aggregate([
      { $match: { category: { $exists: true, $ne: null } } },
      { $group: { _id: '$category', count: { $sum: 1 } } },
      { $sort: { count: -1 } }
    ]).toArray();
    
    // 3. Get all unique post tags
    console.log('Extracting post tags...');
    const postTags = await db.collection('posts').aggregate([
      { $unwind: '$tags' },
      { $group: { _id: '$tags', count: { $sum: 1 } } },
      { $sort: { count: -1 } },
      { $limit: 100 }
    ]).toArray();
    
    // 4. Get post locations
    console.log('Extracting post locations...');
    const postLocations = await db.collection('posts').aggregate([
      { $match: { location: { $exists: true, $ne: null } } },
      { $group: { _id: '$location', count: { $sum: 1 } } },
      { $sort: { count: -1 } },
      { $limit: 30 }
    ]).toArray();
    
    // 5. Sample posts by type (image vs video)
    console.log('Extracting posts by type...');
    const postsByType = await db.collection('posts').aggregate([
      { $group: {
        _id: '$type',
        count: { $sum: 1 },
        avgLikes: { $avg: '$likes' },
        avgBookmarks: { $avg: '$bookmarks' }
      }}
    ]).toArray();
    
    // 6. Sample image posts
    console.log('Extracting sample image posts...');
    const imagePosts = await db.collection('posts').aggregate([
      { $match: { type: 'image' } },
      { $sample: { size: 20 } },
      { $project: {
        title: 1,
        caption: { $substrCP: ['$caption', 0, 100] },
        tags: 1,
        likes: 1,
        bookmarks: 1,
        location: 1,
        hasGallery: { $gt: [{ $size: { $ifNull: ['$gallery', []] } }, 0] }
      }}
    ]).toArray();
    
    // 7. Sample video posts
    console.log('Extracting sample video posts...');
    const videoPosts = await db.collection('posts').aggregate([
      { $match: { type: 'video' } },
      { $sample: { size: 20 } },
      { $project: {
        title: 1,
        caption: { $substrCP: ['$caption', 0, 100] },
        tags: 1,
        likes: 1,
        bookmarks: 1,
        location: 1
      }}
    ]).toArray();
    
    // 8. High engagement posts
    console.log('Extracting high engagement posts...');
    const highEngagementPosts = await db.collection('posts').aggregate([
      { $sort: { likes: -1 } },
      { $limit: 25 },
      { $project: {
        title: 1,
        caption: { $substrCP: ['$caption', 0, 100] },
        tags: 1,
        likes: 1,
        bookmarks: 1,
        type: 1,
        location: 1
      }}
    ]).toArray();
    
    // 9. Get existing albums (collections)
    console.log('Extracting albums...');
    const albums = await db.collection('users').aggregate([
      { $unwind: '$albums' },
      { $project: {
        albumName: '$albums.name',
        albumDescription: '$albums.description',
        isPublic: '$albums.isPublic',
        postCount: { $size: '$albums.postIds' }
      }},
      { $limit: 30 }
    ]).toArray();
    
    // 10. Get unique album names
    console.log('Extracting unique album names...');
    const albumNames = await db.collection('users').aggregate([
      { $unwind: '$albums' },
      { $group: { _id: '$albums.name', count: { $sum: 1 } } },
      { $sort: { count: -1 } }
    ]).toArray();
    
    // 11. Sample comments
    console.log('Extracting sample comments...');
    const sampleComments = await db.collection('posts').aggregate([
      { $unwind: '$comments' },
      { $sample: { size: 25 } },
      { $project: {
        postTitle: '$title',
        commentContent: '$comments.content',
        likeCount: { $size: { $ifNull: ['$comments.likedBy', []] } }
      }}
    ]).toArray();
    
    // 12. User locations
    console.log('Extracting user locations...');
    const userLocations = await db.collection('users').aggregate([
      { $match: { location: { $exists: true, $ne: null } } },
      { $group: { _id: '$location', count: { $sum: 1 } } },
      { $sort: { count: -1 } },
      { $limit: 20 }
    ]).toArray();
    
    // 13. Search history
    console.log('Extracting search history...');
    const searchHistory = await db.collection('searchHistory').find({}, {
      projection: { query: 1 }
    }).toArray();
    
    // 14. Notifications categories and types
    console.log('Extracting notification patterns...');
    const notificationPatterns = await db.collection('notifications').aggregate([
      { $group: {
        _id: { category: '$category', type: '$type' },
        count: { $sum: 1 }
      }},
      { $sort: { count: -1 } }
    ]).toArray();
    
    // 15. Drafts analysis
    console.log('Extracting drafts...');
    const drafts = await db.collection('drafts').find({}, {
      projection: { title: 1, type: 1 }
    }).toArray();
    
    // 16. Posts grouped by common tag themes
    console.log('Analyzing tag themes...');
    const tagThemes = await db.collection('posts').aggregate([
      { $unwind: '$tags' },
      { $group: {
        _id: '$tags',
        posts: { $push: { title: '$title', likes: '$likes' } },
        totalLikes: { $sum: '$likes' },
        count: { $sum: 1 }
      }},
      { $match: { count: { $gte: 2 } } },
      { $sort: { count: -1 } },
      { $limit: 40 },
      { $project: {
        tag: '$_id',
        count: 1,
        totalLikes: 1,
        samplePosts: { $slice: ['$posts', 3] }
      }}
    ]).toArray();
    
    // 17. Users by content specialty (based on their posts' tags)
    console.log('Extracting users by content specialty...');
    const usersBySpecialty = await db.collection('posts').aggregate([
      { $unwind: '$tags' },
      { $group: {
        _id: { userId: '$userId', tag: '$tags' },
        count: { $sum: 1 }
      }},
      { $sort: { count: -1 } },
      { $group: {
        _id: '$_id.userId',
        topTags: { $push: { tag: '$_id.tag', count: '$count' } }
      }},
      { $project: {
        userId: '$_id',
        topTags: { $slice: ['$topTags', 3] }
      }},
      { $limit: 30 }
    ]).toArray();
    
    // 18. Following/Follower relationships sample
    console.log('Extracting social graph sample...');
    const socialGraphSample = await db.collection('users').aggregate([
      { $sample: { size: 15 } },
      { $project: {
        displayName: 1,
        followersCount: { $size: '$followers' },
        followingCount: { $size: '$following' },
        postsCount: { $size: '$posts' },
        category: 1
      }}
    ]).toArray();
    
    const context = {
      extractedAt: new Date().toISOString(),
      summary: {
        totalUsers: users.length,
        totalPosts: await db.collection('posts').countDocuments(),
        totalUniqueTags: postTags.length,
        totalCategories: userCategories.length,
        totalAlbums: albums.length
      },
      userCategories: userCategories.map(c => ({ category: c._id, count: c.count })),
      users,
      postTags: postTags.map(t => ({ tag: t._id, count: t.count })),
      tagThemes,
      postLocations: postLocations.map(l => ({ location: l._id, count: l.count })),
      userLocations: userLocations.map(l => ({ location: l._id, count: l.count })),
      postsByType,
      imagePosts,
      videoPosts,
      highEngagementPosts,
      albums,
      albumNames: albumNames.map(a => ({ name: a._id, count: a.count })),
      sampleComments,
      searchHistory: searchHistory.map(s => s.query),
      notificationPatterns: notificationPatterns.map(n => ({
        category: n._id.category,
        type: n._id.type,
        count: n.count
      })),
      drafts,
      usersBySpecialty,
      socialGraphSample
    };
    
    // Write to file
    fs.writeFileSync('xhs-db-context.json', JSON.stringify(context, null, 2));
    console.log('\n✅ Context extracted to xhs-db-context.json');
    console.log(`   - ${users.length} users`);
    console.log(`   - ${userCategories.length} user categories`);
    console.log(`   - ${postTags.length} unique tags`);
    console.log(`   - ${tagThemes.length} tag themes with multiple posts`);
    console.log(`   - ${postLocations.length} post locations`);
    console.log(`   - ${albums.length} albums`);
    console.log(`   - ${imagePosts.length} sample image posts`);
    console.log(`   - ${videoPosts.length} sample video posts`);
    console.log(`   - ${searchHistory.length} search history entries`);
    
  } finally {
    await client.close();
  }
}

extractContext().catch(console.error);