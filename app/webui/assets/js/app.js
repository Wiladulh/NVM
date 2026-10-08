const $=id=>document.getElementById(id),money=n=>new Intl.NumberFormat('id-ID').format(Number(n)||0);
const esc=s=>String(s??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
function table(rows,cols){if(!rows?.length)return '<p class="hint" style="padding:16px;">Belum ada data.</p>';return '<table><thead><tr>'+cols.map(c=>'<th>'+esc(c)+'</th>').join('')+'</tr></thead><tbody>'+rows.map(r=>'<tr>'+cols.map(c=>'<td>'+esc(r[c])+'</td>').join('')+'</tr>').join('')+'</tbody></table>'}
async function json(url,opt){const r=await fetch(url,opt);let d={};try{d=await r.json()}catch{}return{r,d}}

// Fungsi Kontrol Tab Aktif
function switchTab(tabName) {
  document.querySelectorAll('.tab-pane').forEach(el => el.classList.remove('active'));
  document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
  const pane=$('tab-'+tabName); if(pane)pane.classList.add('active');
  const btn=document.querySelector('.tab-btn[data-tab="'+tabName+'"]'); if(btn)btn.classList.add('active');
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

async function load(){
 try{
  const h=await fetch('/api/v1/health').then(r=>r.json());$('status').textContent='● '+(h.status||'online');
  const d=await fetch('/api/v1/dashboard').then(r=>r.json());
  $('summary').innerHTML=[['Anggota',d.members.length],['Rekening',d.accounts.length],['Pembayaran',d.payments.length],['Pinjaman',d.loans.length],['Vending',d.machines.length],['Perangkat',d.devices.length]].map(x=>'<div class="card"><div class="label">'+x[0]+'</div><div class="value">'+x[1]+'</div></div>').join('');
  $('accounts').innerHTML=table(d.accounts.map(x=>({...x,balance:money(x.balance)})),['account_id','member_name','account_type','balance','status']);
  $('members').innerHTML=table(d.members,['member_id','name','status','created_at']);
  $('payments').innerHTML=table(d.payments.map(x=>({...x,amount:money(x.amount)})),['transaction_id','account_id','amount','method','provider','device_id','status','created_at']);
  $('loans').innerHTML=table(d.loans.map(x=>({...x,principal:money(x.principal),installment_amount:money(x.installment_amount),remaining_balance:money(x.remaining_balance)})),['loan_id','member_id','principal','installment_amount','remaining_balance','status']);
  $('machines').innerHTML=table(d.machines,['machine_id','name','status','last_seen']);
  $('products').innerHTML=table(d.products.map(x=>({...x,price:money(x.price),enabled:x.enabled?'yes':'no'})),['product_id','machine_id','name','price','stock','enabled']);
  $('devices').innerHTML=table(d.devices,['device_id','device_type','status','last_seen']);
 }catch(e){$('status').textContent='● API offline'}
}
async function loadMembers(){
  const token=$('memberAdminToken').value.trim();
  if(!token){$('memberAuthResult').textContent='Admin Token wajib diisi';return}
  try{
    const {r,d}=await json('/api/v1/members',{headers:{'X-NVM-Admin-Token':token}});
    if(!r.ok)throw new Error(d.detail||'Gagal memuat member');
    const rows=d.members||[];
    $('memberAuthResult').textContent='Data member berhasil dimuat.';
    $('members').innerHTML=rows.length?table(rows,['member_id','name','nik','address','status','created_at']):'<p class="hint" style="padding:16px;">Belum ada member terdaftar.</p>';
  }catch(e){$('memberAuthResult').textContent=e.message}
}
$('memberAuthForm').onsubmit=async e=>{e.preventDefault();await loadMembers()};

async function loadDevices(){
  const token=$('deviceAdminToken').value.trim();
  if(!token){$('deviceAuthResult').textContent='Admin Token wajib diisi';return}
  try{
    const {r,d}=await json('/api/v1/devices',{headers:{'X-NVM-Admin-Token':token}});
    if(!r.ok)throw new Error(d.detail||'Gagal memuat perangkat');
    $('deviceAuthResult').textContent='Data perangkat berhasil dimuat.';
    const rows=(d.devices||[]);
    if(!rows.length){$('devices').innerHTML='<p class="hint" style="padding:16px;">Belum ada perangkat terdaftar.</p>';return}
    $('devices').innerHTML='<table><thead><tr><th>Nama Perangkat</th><th>Tipe</th><th>Hardware ID</th><th>MAC</th><th>Status</th><th>Last Seen</th><th>Aksi</th></tr></thead><tbody>'+
      rows.map(x=>'<tr>'+
        '<td><input data-device-name="'+esc(x.device_id)+'" value="'+esc(x.display_name||x.hardware_id)+'" aria-label="Nama Perangkat"></td>'+
        '<td>'+esc(x.device_type)+'</td>'+
        '<td><code>'+esc(x.hardware_id)+'</code></td>'+
        '<td><code>'+esc(x.mac_address||'—')+'</code></td>'+
        '<td><select data-device-status="'+esc(x.device_id)+'">'+['pending','active','offline','maintenance','unassigned','disabled'].map(s=>'<option value="'+s+'"'+(x.status===s?' selected':'')+'>'+s+'</option>').join('')+'</select></td>'+
        '<td>'+esc(x.last_seen||'—')+'</td>'+
        '<td><button type="button" data-device-save="'+esc(x.device_id)+'">Simpan</button></td>'+
      '</tr>').join('')+'</tbody></table>';
    document.querySelectorAll('[data-device-save]').forEach(b=>b.onclick=()=>saveDevice(b.dataset.deviceSave));
  }catch(e){$('deviceAuthResult').textContent=e.message}
}
async function saveDevice(deviceId){
  const token=$('deviceAdminToken').value.trim();
  const name=document.querySelector('[data-device-name="'+CSS.escape(deviceId)+'"]').value.trim();
  const status=document.querySelector('[data-device-status="'+CSS.escape(deviceId)+'"]').value;
  if(!name){$('deviceAuthResult').textContent='Nama perangkat wajib diisi';return}
  try{
    const current=await json('/api/v1/devices/'+encodeURIComponent(deviceId),{headers:{'X-NVM-Admin-Token':token}});
    if(!current.r.ok)throw new Error(current.d.detail||'Gagal membaca perangkat');
    const q={device_type:current.d.device_type,status:status,display_name:name};
    const {r,d}=await json('/api/v1/devices/'+encodeURIComponent(deviceId),{method:'PATCH',headers:{'Content-Type':'application/json','X-NVM-Admin-Token':token},body:JSON.stringify(q)});
    if(!r.ok)throw new Error(d.detail||'Gagal menyimpan perangkat');
    $('deviceAuthResult').textContent='Perangkat berhasil diperbarui.';
    await loadDevices();
  }catch(e){$('deviceAuthResult').textContent=e.message}
}
$('deviceAuthForm').onsubmit=async e=>{e.preventDefault();await loadDevices()};
$('financialForm').onsubmit=async e=>{e.preventDefault();const q={amount:+$('amount').value,reference:$('reference').value||null,idempotency_key:null};const{r,d}=await json('/api/v1/accounts/'+encodeURIComponent($('account').value)+'/'+$('direction').value,{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(q)});$('financialResult').textContent=JSON.stringify(d,null,2);if(r.ok)load()};
$('paymentForm').onsubmit=async e=>{e.preventDefault();const q={credential_id:$('credential').value,account_id:$('payaccount').value,amount:+$('payamount').value,method:$('method').value,provider:$('provider').value||'local',idempotency_key:$('idem').value||null};const{r,d}=await json('/api/v1/payments',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(q)});$('paymentResult').textContent=JSON.stringify(d,null,2);if(r.ok)load()};
$('productForm').onsubmit=async e=>{e.preventDefault();const mid=$('machineId').value.trim(),pid=$('productId').value.trim();const q={product_id:pid,name:$('productName').value.trim(),price:+$('productPrice').value,stock:+$('productStock').value,enabled:$('productEnabled').checked};const{r,d}=await json('/api/v1/vending/'+encodeURIComponent(mid)+'/products/'+encodeURIComponent(pid),{method:'PUT',headers:{'content-type':'application/json'},body:JSON.stringify(q)});$('productResult').textContent=JSON.stringify(d,null,2);if(r.ok)load()};
async function adminToken(){const t=$('adminToken').value.trim();if(!t)throw new Error('Admin Token wajib diisi');return t}
async function loadAudit(){
  try{
    const source=$('auditSource').value, period=$('auditPeriod').value, date=$('auditDate').value;
    const q='?source='+encodeURIComponent(source)+'&period='+encodeURIComponent(period)+(date?'&date='+encodeURIComponent(date):'');
    const token=await adminToken();
    const {r,d}=await json('/api/v1/audit/report'+q,{headers:{'X-NVM-Admin-Token':token}});
    $('auditResult').innerHTML=r.ok?table(d.transactions,['transaction_id','created_at','source','device_id','member_id','account_id','transaction_type','amount','status']):'<p class="hint" style="padding:16px">'+esc(d.detail||'Audit gagal')+'</p>';
  }catch(e){$('auditResult').textContent=e.message}
}
$('auditForm').onsubmit=async e=>{e.preventDefault();await loadAudit()};
$('auditExport').onclick=async()=>{
  try{
    const token=await adminToken();
    const source=$('auditSource').value,period=$('auditPeriod').value,date=$('auditDate').value;
    const q='?source='+encodeURIComponent(source)+'&period='+encodeURIComponent(period)+(date?'&date='+encodeURIComponent(date):'');
    const r=await fetch('/api/v1/audit/export.xlsx'+q,{headers:{'X-NVM-Admin-Token':token}});
    if(!r.ok)throw new Error('Export gagal: '+r.status);
    const blob=await r.blob(),a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='nvm-audit-'+source.toLowerCase()+'-'+period+'.xlsx';a.click();URL.revokeObjectURL(a.href);
  }catch(e){$('auditResult').textContent=e.message}
};
$('operatorPinForm').onsubmit=async e=>{
  e.preventDefault();
  try{
    const token=await adminToken();
    const {r,d}=await json('/api/v1/cashier/operator-pin',{method:'POST',headers:{'Content-Type':'application/json','X-NVM-Admin-Token':token},body:JSON.stringify({pin:$('newOperatorPin').value})});
    $('operatorPinResult').textContent=JSON.stringify(d,null,2);
    if(r.ok)$('newOperatorPin').value='';
  }catch(e){$('operatorPinResult').textContent=e.message}
};
$('backupCreate').onclick=async()=>{
  try{
    const token=await adminToken(),r=await fetch('/api/v1/backup',{method:'POST',headers:{'X-NVM-Admin-Token':token}});
    if(!r.ok)throw new Error('Backup gagal: '+r.status);
    const blob=await r.blob(),a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='NVM_BACKUP.nvm.zip';a.click();URL.revokeObjectURL(a.href);
    $('backupResult').textContent='Backup berhasil dibuat.';
  }catch(e){$('backupResult').textContent=e.message}
};
$('backupRestore').onclick=async()=>{
  try{
    const token=await adminToken(),file=$('restoreFile').files[0];
    if(!file)throw new Error('Pilih file .nvm.zip terlebih dahulu');
    if(!confirm('Restore akan mengganti database aktif. Lanjutkan?'))return;
    const fd=new FormData();fd.append('file',file);
    const {r,d}=await json('/api/v1/backup/restore',{method:'POST',headers:{'X-NVM-Admin-Token':token},body:fd});
    $('backupResult').textContent=JSON.stringify(d,null,2);
    if(r.ok)setTimeout(()=>location.reload(),1000);
  }catch(e){$('backupResult').textContent=e.message}
};
document.querySelectorAll('.tab-btn').forEach(btn=>btn.addEventListener('click',()=>switchTab(btn.dataset.tab)));
load();
