/**
 * The purpose of this script is to set the selected (dropdown) value to whichever the user selected when they
 * ran the query. This will maintain parity with the existing directory.
 * Before this code, the dropdown would always be set to "Name" on the result page
 * even if the user selected another option like "Phone".
 * Has no affect on the search results.
 */


let searchFormField = document.getElementById("query");

document.getElementById("search").onclick = updateSearchSelect;
document.getElementById("method").onchange = updateSearchSelect;

function updateSearchSelect(){
    var value = document.getElementById("method").value;
    searchFormField.setAttribute("name", value);
}
