const bars = document.getElementById('bars');
const navbar = document.getElementById('navbar');
const close = document.getElementById('close');

function showhead(){
    document.getElementById('mycards').style.display('block')
}
function menuFunc(){
    navbar.classList.toggle('show');
}
bars.addEventListener('click',menuFunc);

function menuFuncClose(){
    navbar.classList.toggle('show');
}
close.addEventListener('click',menuFuncClose);