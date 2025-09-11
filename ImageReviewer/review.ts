/** CONFIG **/
const QUEUE_SHEET = 'to review';     // <— your source sheet
const APPROVED_SHEET = 'Approved';
const REJECTED_SHEET = 'Rejected';
// URL is ALWAYS Column B (2)
const URL_COL_INDEX = 2;
/** MENU **/
function onOpen() {
  SpreadsheetApp.getUi()
    .createMenu('Image Review')
    .addItem('Start Review', 'startReview')
    .addToUi();
}
/** UI **/
function startReview() {
  ensureSheets();
  const html = HtmlService.createHtmlOutputFromFile('Review')
    .setTitle('Image Reviewer')
    .setWidth(1600)
    .setHeight(1200);
  SpreadsheetApp.getUi().showModalDialog(html, 'Image Reviewer');
}
/** HELPERS **/
function ensureSheets() {
  const ss = SpreadsheetApp.getActive();
  if (!ss.getSheetByName(QUEUE_SHEET)) ss.insertSheet(QUEUE_SHEET);
  if (!ss.getSheetByName(APPROVED_SHEET)) ss.insertSheet(APPROVED_SHEET);
  if (!ss.getSheetByName(REJECTED_SHEET)) ss.insertSheet(REJECTED_SHEET);
  // No automatic header management - keep it simple
}
function getHeaders(sheet) {
  // Simplified - never try to detect headers, always return empty
  return [];
}
/**
 * Get next item from "to review": the first data row (row 1).
 * Returns { done, rowIndex, url, data, total, remaining }
 */
function getNextItem() {
  const ss = SpreadsheetApp.getActive();
  const q = ss.getSheetByName(QUEUE_SHEET);
  const lastRow = q.getLastRow();
  const lastCol = q.getLastColumn();
  if (lastRow < 1) {
    return { done: true, message: 'No more rows to review.' };
  }
  // Always start from row 1 - no header management
  const dataRange = q.getRange(1, 1, 1, lastCol);
  const rowValues = dataRange.getValues()[0];
  // Safely extract URL from the correct column
  var url = '';
  if (rowValues.length >= URL_COL_INDEX && rowValues[URL_COL_INDEX - 1] != null) {
    url = String(rowValues[URL_COL_INDEX - 1]).trim();
  }
  // Simple data object with generic column names
  var data = {};
  for (let i = 0; i < rowValues.length; i++) {
    data[`Column ${i + 1}`] = rowValues[i];
  }
  return {
    done: false,
    rowIndex: 1,
    url,
    data: data,
    total: lastRow,
    remaining: lastRow
  };
}
/**
 * Get next N items from "to review" starting at row 1.
 * Returns array of { done, rowIndex, url, data, total, remaining }
 */
function getNextItems(count) {
  const ss = SpreadsheetApp.getActive();
  const q = ss.getSheetByName(QUEUE_SHEET);
  const lastRow = q.getLastRow();
  const lastCol = q.getLastColumn();
  if (lastRow < 1) {
    return [{ done: true, message: 'No more rows to review.' }];
  }
  const items = [];
  const rowsToFetch = Math.min(count, lastRow);
  if (rowsToFetch <= 0) {
    return [{ done: true, message: 'No more rows to review.' }];
  }
  // Always start from row 1
  const dataRange = q.getRange(1, 1, rowsToFetch, lastCol);
  const rows = dataRange.getValues();
  for (var i = 0; i < rows.length; i++) {
    var rowValues = rows[i];
    // Safely extract URL from the correct column
    var url = '';
    if (rowValues.length >= URL_COL_INDEX && rowValues[URL_COL_INDEX - 1] != null) {
      url = String(rowValues[URL_COL_INDEX - 1]).trim();
    }
    // Simple data object with generic column names
    var data = {};
    for (var j = 0; j < rowValues.length; j++) {
      data['Column ' + (j + 1)] = rowValues[j];
    }
    items.push({
      done: false,
      rowIndex: 1 + i, // Row position starting from 1
      url: url,
      data: data,
      total: lastRow,
      remaining: lastRow - i,
      // Add unique identifier based on content for duplicate detection
      contentHash: url + '|' + JSON.stringify(data)
    });
  }
  return items;
}
/**
 * Move a row based on decision and delete from "to review".
 * decision: 'approve' | 'reject' | 'skip'
 * rejectionType: optional rejection type for rejected items
 */
function markDecision(rowIndex, decision, rejectionType = '') {
  const ss = SpreadsheetApp.getActive();
  const q = ss.getSheetByName(QUEUE_SHEET);
  const lastCol = q.getLastColumn();
  if (q.getLastRow() < rowIndex) {
    return { ok: false, message: 'Row no longer exists (already processed).' };
  }
  if (decision === 'skip') {
    const rowVals = q.getRange(rowIndex, 1, 1, lastCol).getValues()[0];
    q.deleteRow(rowIndex);
    q.appendRow(rowVals);
    return { ok: true, skipped: true };
  }
  const targetName = decision === 'approve' ? APPROVED_SHEET : REJECTED_SHEET;
  const target = ss.getSheetByName(targetName);
  // Get the row data
  const rowVals = q.getRange(rowIndex, 1, 1, lastCol).getValues()[0];
  // If rejecting, add rejection type to the end
  if (decision === 'reject' && rejectionType) {
    rowVals.push(rejectionType);
  }
  // Simply append the row to the target sheet - no header management
  target.appendRow(rowVals);
  q.deleteRow(rowIndex);
  return { ok: true, movedTo: targetName };
}





10:41
