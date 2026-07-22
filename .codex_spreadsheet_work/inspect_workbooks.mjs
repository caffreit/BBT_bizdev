import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const files = process.argv.slice(2);
for (const file of files) {
  const wb = await SpreadsheetFile.importXlsx(await FileBlob.load(file));
  const sheets = JSON.parse((await wb.inspect({kind:"sheet", include:"id,name", maxChars:10000})).ndjson.trim().split("\n").map(JSON.parse).find(x => x.kind === "sheetCollection")?.data ?? "null");
  console.log(`\nFILE: ${file}`);
  console.log((await wb.inspect({kind:"sheet", include:"id,name", maxChars:10000})).ndjson);
  for (const sheet of wb.worksheets.items) {
    const used = sheet.getUsedRange(true);
    if (!used) { console.log(`SHEET ${sheet.name}: empty`); continue; }
    const vals = used.values;
    console.log(`SHEET ${sheet.name}: ${vals.length} rows x ${Math.max(0,...vals.map(r=>r.length))} cols`);
    console.log(JSON.stringify(vals.slice(0,5)));
  }
}
