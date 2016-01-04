Hello ${fullname},

Congratulations! You have successfully added your ${conf_full_name} ${presentation_type} to the Open Science Framework (OSF).

% if user_created:
Your account on the Open Science Framework has been created. To claim your account, please create a password by clicking here: ${set_password_url}. Please verify your profile information at: ${profile_url}.

% endif
You now have a permanent, citable URL, that you can share: ${node_url}. All submissions for ${conf_full_name} may be viewed at the following link: ${conf_view_url}.

% if is_spam:
Your email was flagged as spam by our mail processing service. To prevent potential spam, we have made your project private. If this is a real project, please log in to your account, browse to your project, and click the "Make Public" button so that other users can view it.

% endif
Get more from the OSF by enhancing your project with the following:

* Collaborators/contributors to the submission
* Charts, graphs, and data that didn't make it onto the submission
* Links to related publications or reference lists
* Connecting other accounts, like Dropbox, Google Drive, GitHub, figshare and Mendeley via add-on integration. Learn more and read the full list of available add-ons: http://osf.io/getting-started/#addons

To learn more about the OSF, visit: http://osf.io/getting-started

Sincerely yours,
The OSF Robot
