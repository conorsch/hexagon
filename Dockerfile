FROM fedora:25
LABEL MAINTAINER="Freedom of the Press Foundation"
LABEL DESCRIPTION="Alternative CLI for managing Qubes OS VMs"
ARG USERID=1000
ARG FEDORA_PKGR_VER=0.6.0.1-1.fc25

RUN echo "Building RPM for Fedora version ${FEDORA_PKGR_VER}"

RUN dnf update -y && \
    dnf install -y \
    fedora-packager-${FEDORA_PKGR_VER}.noarch \
    make \
    python3-cryptography \
    python3-devel \
    python3-requests \
    python3-setuptools \
    vim && \
    yum clean all

ENV HOME /home/user
RUN useradd --create-home --home-dir $HOME user \
    && chown -R user:user $HOME && \
    su -c rpmdev-setuptree user

RUN getent passwd $USERID > /dev/null || \
        ( usermod -u ${USERID} user && chown -R user: /home/user )

ENV SOURCE_DATE_EPOCH 1

WORKDIR /app

USER user

CMD ["./scripts/build-dom0-rpm"]
