const fs=require('fs');
const bytes=fs.readFileSync(process.argv[2]);
WebAssembly.instantiate(bytes,{}).then(({instance})=>{
  const v=instance.exports.run_fixture()>>>0;
  console.log(`WASM_CHECKSUM=${v}`);
}).catch(e=>{console.error(e);process.exit(2);});
