# Installation instructions

Welcome to the installation instructions for greenbot!

Below is the index for a full list of installation instructions for greenbot.

These installation instructions will install greenbot in a way that allows you to run greenbot for multiple streamers at once without too much duplication.
For this reason, these installation instructions are split into two big parts: Installation of greenbot, and creating a greenbot instance for a single channel (which you can repeat as needed, should you want to run greenbot in multiple channels, for different streamers for example).

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

**Table of Contents** _generated with [DocToc](https://github.com/thlorenz/doctoc)_

- [Service installation](#service-installation)
  - [Install system dependencies](#install-system-dependencies)
  - [Set up a system user](#set-up-a-system-user)
  - [Install greenbot](#install-greenbot)
  - [Install and set up the database server](#install-and-set-up-the-database-server)
  - [Install Redis](#install-redis)
  - [Install nginx](#install-nginx)
  - [Install system services](#install-system-services)
- [Single bot setup](#single-bot-setup)
  - [Create a database schema](#create-a-database-schema)
  - [Create a configuration file](#create-a-configuration-file)
  - [Set up the website with nginx](#set-up-the-website-with-nginx)
  - [Enable and start the service](#enable-and-start-the-service)
  - [Further steps](#further-steps)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

# Service installation

Please note we currently only document how to run greenbot on GNU/Linux systems. The following instructions should work without any changes on Debian and Ubuntu. If you are running another distribution of GNU/Linux, you might have to make some changes to the commands, file locations, etc. below.

## Install system dependencies

Greenbot is written in python, so we need to install some basic python packages:

```bash
sudo apt update
sudo apt install python3 python3-pip python3-venv
```

We also need the following libraries:

```bash
sudo apt install libssl-dev libpq-dev
```

## Set up a system user

For security reasons, you shouldn't run greenbot as the `root` user on your server.
You can create a low-privilege "system" user for greenbot like this:

```bash
sudo adduser --system --group greenbot --home /opt/greenbot
```

## Install greenbot

Download the latest stable version of greenbot:

```bash
sudo -u greenbot git clone https://github.com/TroyDota/greenbot.git
```

Install greenbot's dependencies like this:

```bash
cd /opt/greenbot
sudo -u greenbot ./scripts/venvinstall.sh
```

## Install and set up the database server

greenbot uses PostgreSQL as its database server. If you don't already have PostgreSQL running on your server, you can install it with:

```bash
sudo apt install postgresql
```

Now that you have PostgreSQL installed, we will create a user to allow greenbot to use the PostgreSQL database server:

```bash
sudo -u postgres createuser greenbot
```

> Note: We have not set a password for greenbot, and this is intentional. Because we created a system user with the name `greenbot` earlier, applications running under the `greenbot` system user will be able to log into the database server as the `greenbot` database user automatically, without having to enter a password.
>
> We have run `createuser` as `postgres` for the same reason: `postgres` is a pre-defined PostgreSQL database superuser, and by using `sudo`, we are executing `createuser greenbot` as the `postgres` system (and database) user.
>
> This is a default setting present on Debian-like systems, and is defined via the configuration file [`pg_hba.conf`](https://www.postgresql.org/docs/current/auth-pg-hba-conf.html).

We will now create a database named `greenbot`, owned by the `greenbot` database user:

```bash
sudo -u greenbot createdb --owner=greenbot greenbot
```

## Install Redis

greenbot also needs an instance of [Redis](https://redis.io/) to run.
The redis database server does not need any manual setup - all you have to do is install redis:

```bash
sudo apt install redis-server
```

The redis server is automatically started after installation. You can verify your installation works like this:

```bash
redis-cli PING
```

You should get `PONG` as the response output. That means your redis server is working fine.

## Install nginx

Nginx is a reverse proxy - it accepts all incoming HTTP requests to your server, and forwards the request to the correct backend service. It also applies encryption for HTTPS, can set headers, rewrite URLs, and so on.

All you need to do for this step is to install nginx:

```bash
sudo apt install nginx
```

We will configure nginx later.

> Note: You can find a basic nginx configuration setup including HTTP -> HTTPS redirect, recommended SSL configuration parameters, etc. [over here](./full-nginx-setup/README.md).
> If you don't already have a basic nginx setup, we strongly recommend you follow the linked guideline now.

## Install system services

We recommend you run greenbot with the help of systemd. Systemd will take care of:

- starting and stopping greenbot,
- capturing and storing the output of the service as logs,
- starting greenbot automatically on system startup (and starting it in the correct order, after other services it needs),
- restarting greenbot on failure,
- and running multiple instances if you run greenbot for multiple streamers

To start using systemd for greenbot, install the pre-packaged unit files like this:

```bash
sudo cp /opt/greenbot/install-docs/*.service /etc/systemd/system/
```

Then tell systemd to reload changes:

```bash
sudo systemctl daemon-reload
```

# Single bot setup

Now that you have the basics installed, we need to tell greenbot to (and how to) run in a certain channel. Greenbot running in a single channel, and with its website for that channel, is called an **instance** of greenbot from now on.

## Create a database schema

Each instance's data lives in the same database (`greenbot`, we created this earlier), but we separate the data by putting each instance into its own **schema**. To create a new schema for your instance, run:

```bash
sudo -u greenbot psql greenbot -c "CREATE SCHEMA greenbot_name"
```

Remember the name of the schema you created! You'll need to enter it into the configuration file, which you will create and edit in the next step:

## Create a configuration file

There is an [example config file](../configs/example.ini) available for you to copy:

```bash
sudo -u greenbot cp /opt/greenbot/configs/example.ini /opt/greenbot/config/name.ini
```

The example config contains comments about what values you need to enter in what places. Edit the config with a text editor to adjust the values.

```bash
sudo -u greenbot editor /opt/greenbot/configs/name.ini
```

## Set up the website with nginx

greenbot comes with pre-set nginx configuration files you only need to copy and edit lightly to reflect your installation.

```bash
sudo cp /opt/greenbot/install-docs/nginx-example.conf /etc/nginx/sites-available/your-domain.com.conf
sudo ln -s /etc/nginx/sites-available/your-domain.com.conf /etc/nginx/sites-enabled/
```

You have to then edit the file, at the very least you will have to insert the correct streamer name instead of the example streamer name.

The example configuration sets your website up over HTTPS, for which you need a certificate (`ssl_certificate` and `ssl_certificate_key`). There are many possible ways to get a certificate, which is why we can't offer a definitive guide that will work for everybody's setup. However, if you need help for this step, you can [find a guide here](./certbot-with-cloudflare/README.md) if you have set up your domain with **CloudFlare DNS**.

Once you're done with your changes, test that the configuration has no errors:

```bash
sudo nginx -t
```

If this check is OK, you can now reload nginx:

```bash
sudo systemctl reload nginx
```

## Enable and start the service

To start and enable (i.e. run it on boot) greenbot, run:

```bash
sudo systemctl enable --now greenbot@name greenbot-web@name
```

Then, to finally make the bot come online, run:

```bash
sudo systemctl restart greenbot@name
```

## Further Steps
```
  !add command points --allow_whisper $(member;1:mention) has $(user;1:points) $(currency:name)
  !add command commands --allow_whisper $(member;1:mention), $(commands)
  !add command commandinfo --allow_whisper $(member;1:mention), $(commandinfo;1)
  !add command roleinfo $(member;1:mention), $(roleinfo;1)
  !add command userinfo $(member;1:mention), $(userinfo;1)
  !add command avatar $(member;1:mention), $(userinfo;1)

  !add funccommand kick --level 1000 --privatemessage --function $(kick;$(1);$(2)) 
  !add funccommand ban --level 1000 --privatemessage --function $(banmember;$(1);$(2);$(3);$(rest:3))
  !add funccommand unban --level 1000 --privatemessage --function $(unbanmember;$(1);$(rest:1))
  !add funccommand level --level 1500 --privatemessage --function $(level;$(1);$(2))
```
