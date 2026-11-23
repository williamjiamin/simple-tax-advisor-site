const [data, translations, faq] = await Promise.all([
 fetch("../data/tax_schedules.json").then(r=>r.json()),
 fetch("i18n.json").then(r=>r.json()),
 fetch("faq.schema.json").then(r=>r.json())
]);
document.querySelector("#faq-data").textContent = JSON.stringify(faq);
const locale = document.querySelector("#language");
function tax(income, brackets){let total=0,lo=0;for(const b of brackets){const hi=b.up_to;total+=Math.max(0,(hi===null?income:Math.min(income,hi))-lo)*b.rate;if(hi===null||income<=hi)break;lo=hi;}return total;}
function render(){const lang=locale.value,t=translations[lang],income=Number(document.querySelector("#income").value);
document.documentElement.lang=lang;document.querySelector("#title").textContent=t.title;document.querySelector("#subtitle").textContent=t.subtitle;document.querySelector("#disclaimer").textContent=t.disclaimer;
document.querySelector("#income-value").textContent=income.toLocaleString(lang);
document.querySelector("#results").innerHTML=data.jurisdictions.map(j=>{const amount=tax(income,j.brackets);return `<article class="result"><span>${j.label[lang]}</span><strong>${amount.toLocaleString(lang,{maximumFractionDigits:0})}</strong><small>${income?((amount/income)*100).toFixed(1):"0.0"}% effective illustrative rate</small></article>`}).join("");
}
locale.addEventListener("change",render);document.querySelector("#income").addEventListener("input",render);render();
