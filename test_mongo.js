const { MongoClient } = require('mongodb');

const uri = "mongodb+srv://mrityunjaygupta:dYuyQzS24KtAI2Ez@sequeldev-expense.l3ygq.mongodb.net/VaOM_CLM_DEV?retryWrites=true&w=majority";
const client = new MongoClient(uri);

async function run() {
  try {
    await client.connect();
    const db = client.db('VaOM_CLM_DEV');
    const rfq = await db.collection('rfqs').findOne();
    const bid = await db.collection('vendorbids').findOne();
    console.log("Sample RFQ:", JSON.stringify(rfq, null, 2));
    console.log("Sample Bid:", JSON.stringify(bid, null, 2));
  } finally {
    await client.close();
  }
}
run().catch(console.dir);
