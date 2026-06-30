import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";
const files = process.argv.slice(2);
for (const path of files) {
  try {
    const input = await FileBlob.load(path);
    const wb = await SpreadsheetFile.importXlsx(input);
    const info = await wb.inspect({ kind: "sheet", include: "id,name", maxChars: 4000 });
    console.log("FILE", path);
    console.log(info.ndjson);
  } catch (e) {
    console.log("ERROR", path, e.message);
  }
}
