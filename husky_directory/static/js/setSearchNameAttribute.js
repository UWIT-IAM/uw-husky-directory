let searchformfield = document.getElementById("name");
document.getElementById("method").onchange = changeListener;

function changeListener(){
    var value = this.value
    searchformfield.setAttribute("name", value);
}
