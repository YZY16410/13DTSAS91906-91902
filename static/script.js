function toggleSecretKey(){
    var roleSelect = document.getElementById('role-select')
    var secretWrap = document.getElementById('admin-secret-wrap');
    var secretKeyInput = document.getElementById('admin-secret-key')

    if (roleSelect.value == "admin"){
        secretWrap.style.display = "block"
        secretKeyInput.setAttribute("required", "required")
    } else {
        secretWrap.style.display = "none"
        secretKeyInput.removeAttribute("required") 
    }
}