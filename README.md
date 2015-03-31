plexforboxee - A Plex Client for Boxee
================================
Originally created by Mike McMullin (xmcnuggetx)  and currently being developed by Grant McWilliams https://github.com/grantmcwilliams

---

The code is not complete - but the core functionality (browsing videos and streaming) works. As of February 23, 2014 the app is installable from the plexforboxee custom app repository outlined below. 

TODO
* Add playing videos from Queue (in latest release for testing now)
* Get Video Channels to work (in latest release for testing now)


Manual Install Instructions
---------------------------

_**As of 31-Mar-2015 the Boxee application signing at http://boxee.tv is not working. So the latest release will not be available via the repository until this is fixed. To install the latest version use Options 2 or 3.**_

*Option 1* - plexforboxee 1.10 in repository (all patches merged as of Oct 26, 2014)

1. Navigate to Apps -> Repositories on your Boxee
2. Click the + button on the top right to add the PlexforBoxee repository - http://grantmcwilliams.com/plexforboxee
3. Browse the PlexforBoxee repository and add the Plexee App


*Option 2* - If you have root access to your Boxee (via Boxee+hacks - http://boxeed.in)

1. Remove the current Plexee repository and existing application from Boxee
2. Download the zip from Git, and extract locally
3. Modify the descriptor.xml file in the plexee.plexforboxee folder
Add the following above the `</app>` closing tag
<pre>
`        <test-app>true</test-app>
</app>`
</pre>
4. Copy only the plexee.plexforboxee folder to /data/.boxee/UserData/apps

*Option 3* - If you have a closed device - then you'll need to get a developers certificate for your device.

1. Login to your boxee account at http://www.boxee.tv
2. Go to the Developer section and follow the process to get a certificate
3. Copy the certificate into a folder name BoxeeApps on the root of a usb stick/drive
4. Copy the plexee folder into BoxeeApps as well
5. Attach the usb stick/drive to the Boxee device - the plexee application should now be available under Favourites in Apps

