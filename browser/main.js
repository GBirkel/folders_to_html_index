

// -1 : Print as a full float
//  0 : Print as an int, ALWAYS rounded down.
// +n : Print with n decimal places, UNLESS the value is an integer
function nicelyPrintFloat(v, places) {
  // We do not want to display ANY decimal point if the value is an integer.
  if (v % 1 === 0) {	// Basic integer test
    return (v % 1).toString();
  }
  if (places > 0) {
    return v.toFixed(places);
  } else if (places == 0) {
    return (v % 1).toString();
  }
  return v.toString();
}


// Convert a size provided in bytes to a nicely formatted string
function sizeToString(size) {

  var tb = size / (1024 * 1024 * 1024 * 1024);
  if ((tb > 1) || (tb < -1)) {
    return nicelyPrintFloat(tb, 2) + ' Tb';
  }
  var gigs = size / (1024 * 1024 * 1024);
  if ((gigs > 1) || (gigs < -1)) {
    return nicelyPrintFloat(gigs, 2) + ' Gb';
  }
  var megs = size / (1024 * 1024);
  if ((megs > 1) || (megs < -1)) {
    return nicelyPrintFloat(megs, 2) + ' Mb';
  }
  var k = size / 1024;
  return nicelyPrintFloat(k, 2) + ' Kb';
}


// Given a date in seconds (with a possible fractional portion being milliseconds),
// based on zero being midnight of Jan 1, 1970 (standard old-school POSIX time),
// return a string formatted in the manner of "Dec 21 2012, 11:45am",
// with exceptions for 'Today' and 'Yesterday', e.g. "Yesterday, 3:12pm".
function timestampToTodayString(timestamp) {

  // Code adapted from Perl's HTTP-Date
  //var DoW = ['Sun','Mon','Tue','Wed','Thu','Fri','Sat'];
  var MoY = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];

  if (!timestamp || timestamp < 1) {
    return '<span style="color:#888;">N/A</span>';
  }

  var t = new Date(Math.round(timestamp*1000));
  var n = new Date();
  var now = n.getTime();

  var sec = t.getSeconds();
  var min = t.getMinutes();
  var hour = t.getHours();
  var mday = t.getDate();		// Returns the day of the month (from 1-31)
  var mon = t.getMonth();		// Returns the month (from 0-11)
  var year = t.getFullYear();	// Returns the year (four digits)
  var wday = t.getDay();		// Returns the day of the week (from 0-6)

  var nsec = n.getSeconds();
  var nmin = n.getMinutes();
  var nhour = n.getHours();
  var nmday = n.getDate();
  var nmon = n.getMonth();
  var nyear = n.getFullYear();

  var day_str;

  if ((year == nyear) && (mon == nmon) && (mday == nmday)) {
    day_str = 'Today';
  } else if (	    (now - (nsec + (60*(nmin+(60*(nhour+24)))))) ==		// Now's day component minus a day
            (timestamp - (sec  + (60*(min +(60* hour     ))))))	 {	// Timestamp's day component
    day_str = 'Yesterday';
  } else {
    var year_str = '';
    if (year != nyear) {
      year_str = ' ' + year;
    }
    day_str = MoY[mon] + ' ' + mday + year_str;
  }

  var half_day = 'am';
  if (hour > 11) {half_day = 'pm';}
  if (hour > 12) {hour -= 12;}
  else if (hour == 0) {hour = 12;}
  if (min < 9) {min = '0'+min;}

  return day_str + ', ' + hour + ':' + min + half_day;
}


function generateDistinctHSLColors(count) {
  const colors = [];
  for (let i = 0; i < count; i++) {
    const hue = Math.round((360 / count) * i);
    colors.push(`hsl(${hue}, 95%, 20%)`);
  }
  return colors;
}


async function onLoad() {

  var card_colors = generateDistinctHSLColors(card_data.length);
  // Map card IDs to colors
  for (let i = 0; i < card_data.length; i++) {
    card_data[i].color = card_colors[i];
  }

  var card_data_by_id = {};
  for (const card of card_data) {
    card_data_by_id[card.id] = card;
  }

  var folder_data_by_id = {};
  for (const folder of folder_data) {
    // Map folder data to include card color
    const card = card_data_by_id[folder.card_id];
    folder.card_color = card ? card.color : 'gray';
    folder.card_name = card ? card.name : 'Unknown Card';
    folder_data_by_id[folder.id] = folder;
  }

  var file_data_by_id = {};
  var file_ids = [];
  for (const file of file_data) {
    // Map file data to include card color
    const card = card_data_by_id[file.card_id];
    file.card_color = card ? card.color : 'gray';
    file.card_name = card ? card.name : 'Unknown Card';
    file_data_by_id[file.id] = file;
    file_ids.push(file.id);
  }

  const file_ids_sorted = file_ids.sort((a, b) => {
    const fileA = file_data_by_id[a];
    const fileB = file_data_by_id[b];
    return fileA.pathname.localeCompare(fileB.pathname);
  });

  const searchField = document.getElementById('searchField');

  const onSearchInput = function() {

    const query = searchField.value.toLowerCase();
    const results = file_ids_sorted.filter(id => {
      const file = file_data_by_id[id];
      return file.pathname.toLowerCase().includes(query);
    });

    const tbody = document.getElementById('result_rows');

    tbody.innerHTML = '';
    for (const id of results) {
      const file = file_data_by_id[id];
      const tr = document.createElement('tr');
      tr.style.backgroundColor = file.card_color;
      tr.title = `On card: ${file.card_name}`;
      tr.innerHTML = `
        <td>${file.pathname}</td><td class="size">${sizeToString(file.size)}</td>
      `;
      tbody.appendChild(tr);
    }
  }

  var searchDebounceTimer = null;
  const onSearchInputDebouncer = function() {
    if (searchDebounceTimer) { clearTimeout(searchDebounceTimer); }
    searchDebounceTimer = setTimeout(onSearchInput, 300); // Debounce for 300ms
  }

  searchField.addEventListener('input', onSearchInputDebouncer);

  // Initial render
  onSearchInput();
}
