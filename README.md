# profiler
Home Assistant Profiler

The profiler can be installed via HACS by adding `https://github.com/bdraco/profiler.git` as a custom repository.

Then setup the Profile integration

<img width="787" alt="Screen Shot 2020-10-03 at 8 55 58 AM" src="https://user-images.githubusercontent.com/663432/94993383-46ea0400-0556-11eb-94fd-868d8267eb7e.png">

Once its up an running call the `profiler.start` service.

<img width="530" alt="Screen Shot 2020-10-03 at 8 54 51 AM" src="https://user-images.githubusercontent.com/663432/94993366-24f08180-0556-11eb-98f6-7352b09a9183.png">

This will generate a `profile.TIMESTAMP.cprof` and `callgrind.out.TIMESTAMP` file in your home assistant directory after 60 seconds.

<img width="496" alt="Screen Shot 2020-10-03 at 8 56 57 AM" src="https://user-images.githubusercontent.com/663432/94993401-6b45e080-0556-11eb-926b-f178aa6d4fe6.png">
<img width="482" alt="Screen Shot 2020-10-03 at 8 57 58 AM" src="https://user-images.githubusercontent.com/663432/94993433-8e709000-0556-11eb-9d67-2700f8d002f5.png">

To watch growth of objects in memory of time.
<img width="624" alt="Screen Shot 2020-11-07 at 11 55 10 AM" src="https://user-images.githubusercontent.com/663432/98452086-39dda900-20f0-11eb-9d90-80555d455ffc.png">

...and then dump intresting objects to the log:
<img width="610" alt="Screen Shot 2020-11-07 at 11 55 22 AM" src="https://user-images.githubusercontent.com/663432/98452084-377b4f00-20f0-11eb-993d-ab77757a3858.png">
