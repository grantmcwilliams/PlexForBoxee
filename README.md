plexforboxee - A Plex Client for Boxee
================================
Originally created by Mike McMullin (xmcnuggetx)  and currently being developed by Grant McWilliams https://github.com/grantmcwilliams

---

The code is currently buggy - but the core functionality (browsing videos and streaming) works. As of February 23, 2014 the app is installable from the plexforboxee custom app repository outlined below. 

TODO
* Fix exit from video bug that crashes the app
* Add integration with myplex service
* Fix bugs in photo and music playing areas
* Remove Auto discover and MyPlex from Settings dialog until they work
* Change settings dialog so that you can't select MyPlex AND Manual AND Auto discover


Manual Install Instructions
---------------------------

*Option 1*
* Navigate to Apps -> Repositories on your Boxee
* Click the + button on the top right to add the PlexforBoxee repository - http://grantmcwilliams.com/plexforboxee
* Browse the PlexforBoxee repository and add the Plexee App
* Manual configure Plexee using the Plexee app
* Enter the IP address of your Plex Media Server
* Enter the port number of your Plex Media Server (default is 32400)


*Option 2*
* If you have root access to your Boxee (via Boxee+hacks - http://boxeeplus.com) - copy the plexee app into /data/.boxee/UserData/apps

*Option 3*
* If you have a closed device - then you'll need to get a developers certificate for your device.
* Login to your boxee account at http://www.boxee.tv
* Go to the Developer section and follow the process to get a certificate
* Copy the certificate into a folder name BoxeeApps on the root of a usb stick/drive
* Copy the plexee folder into BoxeeApps as well
* Attach the usb stick/drive to the Boxee device - the plexee application should now be available under Favourites in Apps

