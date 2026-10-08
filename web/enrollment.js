/* Consent is persisted by the local service. There is no research upload path. */
async function initEnrollment(){
 const dialog=document.createElement('dialog');dialog.id='enrollment';
 dialog.innerHTML=`<h2>Welcome to Bandstand</h2><p>Your writing, EEG, embeddings and personal decoder stay on this computer.</p>
 <details><summary>Privacy notice · October 8, 2026</summary><p>Recording starts only when you choose Start. Across-app writing capture can include sensitive text; stop recording before entering anything you do not want saved. Display redaction does not remove text from saved records.</p><p>Local files are not yet encrypted by Bandstand. Your computer’s permissions, disk encryption and backup settings govern access. Researchers cannot retrieve these local records through this app.</p><p>Optional ERP sharing will let authorized researchers access individual recordings under standard encryption and access controls. It will not use secure aggregation or differential privacy. Shared recordings will be retained until you request deletion; backup expiration must be specified before sharing opens.</p><p>Shared decoder training is not available yet. We will request new consent after secure aggregation and participant-level differential privacy have been implemented and tested. Deleting contributions cannot automatically remove their influence from an already trained model.</p><p>Research contact: Andrew Neff. Email: <a href="mailto:aneff8626@gmail.com">aneff8626@gmail.com</a>. This is a local preview of enrollment; no data uploads are enabled.</p></details>
 <fieldset><legend>Account</legend><label>Email<input id="accountEmail" type="email" autocomplete="username"></label><label>Password<input id="accountPassword" type="password" autocomplete="current-password"></label><div class="button-row"><button id="accountSignIn">Sign in</button><button id="accountSignUp">Create account</button><button id="accountSignOut" hidden>Sign out</button><button id="accountRecover">Forgot password?</button></div><details id="accountRecoverySection"><summary>Reset password in Bandstand</summary><p>Request an email with Forgot password. Enter its code, or copy the reset link without opening it and paste it below. No password is entered on GitHub.</p><label>Recovery code or unopened link<input id="accountRecoveryCode" type="password" autocomplete="one-time-code"></label><label>New password<input id="accountNewPassword" type="password" autocomplete="new-password"></label><label>Repeat new password<input id="accountNewPasswordAgain" type="password" autocomplete="new-password"></label><button id="accountReset">Save new password</button></details><details id="accountDeleteSection" hidden><summary>Delete my cloud account</summary><p>This permanently deletes your Supabase account and consent record. No research uploads are enabled. Local recordings are kept. This does not erase provider backups immediately.</p><label>Type DELETE to confirm<input id="accountDeleteConfirm" autocomplete="off"></label><button id="accountDelete">Delete cloud account</button></details><p id="accountStatus" role="status"></p><p>Optional: account credentials go to Supabase over HTTPS. Your password is not saved by Bandstand; sign-in tokens stay in memory until sign-out or app exit. No recordings are uploaded. Local use does not require an account.</p></fieldset>
 <label><input id="erpConsent" type="checkbox"> I would like to share ERP recordings with the research team.</label><p class="muted">Preference only. No upload will occur; confirmation will be required when sharing becomes available.</p>
 <label><input type="checkbox" disabled> Contribute to shared decoder training — not yet available</label>
 <label><input id="privacyAgree" type="checkbox"> I have read the privacy notice.</label>
 <p id="enrollmentError" role="alert"></p><button id="saveEnrollment" class="primary">Save choices & use locally</button>`;
 document.body.append(dialog);
 const button=document.createElement('button');button.textContent='Privacy & sharing';button.onclick=()=>dialog.showModal();document.querySelector('nav').append(button);
 const accountStatus=document.getElementById('accountStatus');
 const renderAccount=a=>{accountStatus.textContent=a.signed_in?'Signed in as '+a.email:a.message||'Not signed in';document.getElementById('accountSignOut').hidden=!a.signed_in;document.getElementById('accountDeleteSection').hidden=!a.signed_in};
 for(const [id,action] of [['accountSignIn','signin'],['accountSignUp','signup'],['accountSignOut','signout']])document.getElementById(id).onclick=async()=>{
  const controls=['accountSignIn','accountSignUp','accountSignOut'].map(x=>document.getElementById(x));controls.forEach(x=>x.disabled=true);
  try{renderAccount(await api('account/'+action,{email:document.getElementById('accountEmail').value,password:document.getElementById('accountPassword').value}))}catch(e){accountStatus.textContent=e.message}finally{document.getElementById('accountPassword').value='';controls.forEach(x=>x.disabled=false)}
 };
 document.getElementById('accountRecover').onclick=async()=>{
  const button=document.getElementById('accountRecover');button.disabled=true;
  document.getElementById('accountPassword').value='';
  try{const result=await api('account/recover',{email:document.getElementById('accountEmail').value});accountStatus.textContent=result.message}catch(e){accountStatus.textContent=e.message}finally{button.disabled=false}
 };
 document.getElementById('accountReset').onclick=async()=>{
  const button=document.getElementById('accountReset'),password=document.getElementById('accountNewPassword'),again=document.getElementById('accountNewPasswordAgain'),code=document.getElementById('accountRecoveryCode');
  if(password.value!==again.value){accountStatus.textContent='The new passwords do not match.';return}
  button.disabled=true;
  try{renderAccount(await api('account/reset',{email:document.getElementById('accountEmail').value,code:code.value,password:password.value}))}catch(e){accountStatus.textContent=e.message}finally{password.value='';again.value='';code.value='';button.disabled=false}
 };
 document.getElementById('accountDelete').onclick=async()=>{const button=document.getElementById('accountDelete');button.disabled=true;try{renderAccount(await api('account/delete',{confirmation:document.getElementById('accountDeleteConfirm').value}));document.getElementById('accountDeleteConfirm').value=''}catch(e){accountStatus.textContent=e.message}finally{button.disabled=false}};
 renderAccount(await api('account/status'));
 const status=await api('enrollment');
 document.getElementById('erpConsent').checked=status.consent.erp_sharing_requested===true;
 document.getElementById('privacyAgree').checked=status.consent.policy_version===status.policy_version&&status.consent.acknowledged===true;
 document.getElementById('saveEnrollment').onclick=async()=>{try{await api('enrollment',{policy_version:status.policy_version,acknowledged:document.getElementById('privacyAgree').checked,erp_sharing_requested:document.getElementById('erpConsent').checked});dialog.close()}catch(e){document.getElementById('enrollmentError').textContent=e.message}};
 if(!document.getElementById('privacyAgree').checked)dialog.showModal();
}
