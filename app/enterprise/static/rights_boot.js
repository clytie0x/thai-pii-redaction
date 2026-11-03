import { mountRightsStaff, mountRightsSubject } from './rights_ui.js';
if (document.body.dataset.rightsLane === 'staff') mountRightsStaff();
if (document.body.dataset.rightsLane === 'subject') mountRightsSubject();
