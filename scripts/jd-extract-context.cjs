// scripts/jd-extract-context.js
// Run: node scripts/jd-extract-context.js
// Output: jd-db-context.json

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
    
    // 1. Get all unique categories
    console.log('Extracting categories...');
    const categories = await db.collection('products').distinct('category');
    
    // 2. Get all unique brands
    console.log('Extracting brands...');
    const brands = (await db.collection('products').distinct('brand')).filter(Boolean);
    
    // 3. Get price ranges by category
    console.log('Extracting price ranges...');
    const priceRanges = await db.collection('products').aggregate([
      { $group: {
        _id: '$category',
        minPrice: { $min: '$currentPrice' },
        maxPrice: { $max: '$currentPrice' },
        avgPrice: { $avg: '$currentPrice' },
        count: { $sum: 1 }
      }},
      { $sort: { count: -1 } }
    ]).toArray();
    
    // 4. Get variant types and their options
    console.log('Extracting variants...');
    const variantData = await db.collection('products').aggregate([
      { $unwind: '$variants' },
      { $unwind: '$variants.options' },
      { $group: { 
        _id: '$variants.label', 
        options: { $addToSet: '$variants.options.label' },
        count: { $sum: 1 }
      }},
      { $sort: { count: -1 } }
    ]).toArray();
    
    // 5. Sample products with variants (for specific variant tasks)
    console.log('Extracting sample products with variants...');
    const productsWithVariants = await db.collection('products').aggregate([
      { $match: { 'variants.0': { $exists: true } } },
      { $sample: { size: 25 } },
      { $project: {
        title: 1,
        category: 1,
        brand: 1,
        currentPrice: 1,
        variants: {
          $map: {
            input: '$variants',
            as: 'v',
            in: {
              label: '$$v.label',
              options: { $map: { input: '$$v.options', as: 'o', in: '$$o.label' } }
            }
          }
        }
      }}
    ]).toArray();
    
    // 6. Products with promotions
    console.log('Extracting products with promotions...');
    const productsWithPromos = await db.collection('products').aggregate([
      { $match: { 'promotions.0': { $exists: true } } },
      { $sample: { size: 15 } },
      { $project: {
        title: 1,
        category: 1,
        currentPrice: 1,
        promotions: '$promotions.text'
      }}
    ]).toArray();
    
    // 7. Get promotion types that exist
    console.log('Extracting promotion types...');
    const promotionTypes = await db.collection('products').aggregate([
      { $unwind: '$promotions' },
      { $group: {
        _id: '$promotions.text',
        count: { $sum: 1 }
      }},
      { $sort: { count: -1 } },
      { $limit: 20 }
    ]).toArray();
    
    // 8. General sample products
    console.log('Extracting general sample products...');
    const sampleProducts = await db.collection('products').aggregate([
      { $sample: { size: 30 } },
      { $project: {
        title: 1,
        category: 1,
        brand: 1,
        currentPrice: 1,
        originalPrice: 1,
        rating: 1,
        stockStatus: 1
      }}
    ]).toArray();
    
    // 9. Stores
    console.log('Extracting stores...');
    const stores = await db.collection('stores').find({}, {
      projection: { name: 1, categories: 1, isOfficial: 1, rating: 1, tags: 1 }
    }).toArray();
    
    // 10. Review tags across products
    console.log('Extracting review tags...');
    const reviewTags = await db.collection('productMeta').aggregate([
      { $unwind: '$reviewTags' },
      { $group: {
        _id: '$reviewTags.label',
        totalCount: { $sum: '$reviewTags.count' }
      }},
      { $sort: { totalCount: -1 } },
      { $limit: 30 }
    ]).toArray();
    
    // 11. Sample specs labels (what specifications exist)
    console.log('Extracting spec labels...');
    const specLabels = await db.collection('productMeta').aggregate([
      { $unwind: '$specs' },
      { $group: {
        _id: '$specs.label',
        sampleValues: { $addToSet: '$specs.value' },
        count: { $sum: 1 }
      }},
      { $project: {
        _id: 1,
        count: 1,
        sampleValues: { $slice: ['$sampleValues', 5] }
      }},
      { $sort: { count: -1 } },
      { $limit: 25 }
    ]).toArray();
    
    // 12. Sample Q&A questions
    console.log('Extracting sample Q&A...');
    const sampleQA = await db.collection('productMeta').aggregate([
      { $unwind: '$productQA' },
      { $sample: { size: 20 } },
      { $project: {
        question: '$productQA.question',
        answerCount: { $size: '$productQA.answers' }
      }}
    ]).toArray();
    
    // 13. Search history queries
    console.log('Extracting search history...');
    const searchQueries = await db.collection('searchHistory').find({}, {
      projection: { query: 1 }
    }).toArray();
    
    // 14. Products by rating ranges
    console.log('Extracting rating distribution...');
    const ratingDistribution = await db.collection('products').aggregate([
      { $match: { rating: { $exists: true } } },
      { $bucket: {
        groupBy: '$rating',
        boundaries: [0, 4.0, 4.5, 4.7, 4.9, 5.1],
        default: 'unknown',
        output: {
          count: { $sum: 1 },
          sampleProducts: { $push: { title: '$title', category: '$category' } }
        }
      }}
    ]).toArray();
    
    const context = {
      extractedAt: new Date().toISOString(),
      summary: {
        totalCategories: categories.length,
        totalBrands: brands.length,
        totalStores: stores.length,
        totalPromotionTypes: promotionTypes.length
      },
      categories,
      brands,
      priceRanges,
      variantTypes: variantData.map(v => ({
        type: v._id,
        options: v.options.slice(0, 15), // Limit options for readability
        productCount: v.count
      })),
      promotionTypes: promotionTypes.map(p => ({ text: p._id, count: p.count })),
      reviewTags: reviewTags.map(t => ({ label: t._id, count: t.totalCount })),
      specLabels: specLabels.map(s => ({ 
        label: s._id, 
        count: s.count,
        sampleValues: s.sampleValues 
      })),
      sampleQA,
      productsWithVariants,
      productsWithPromos,
      sampleProducts,
      stores,
      searchQueries: searchQueries.map(s => s.query),
      ratingDistribution
    };
    
    // Write to file
    fs.writeFileSync('jd-db-context.json', JSON.stringify(context, null, 2));
    console.log('\n✅ Context extracted to jd-db-context.json');
    console.log(`   - ${categories.length} categories`);
    console.log(`   - ${brands.length} brands`);
    console.log(`   - ${stores.length} stores`);
    console.log(`   - ${productsWithVariants.length} products with variants`);
    console.log(`   - ${productsWithPromos.length} products with promotions`);
    console.log(`   - ${promotionTypes.length} unique promotion types`);
    console.log(`   - ${reviewTags.length} review tag types`);
    console.log(`   - ${specLabels.length} specification labels`);
    
  } finally {
    await client.close();
  }
}

extractContext().catch(console.error);