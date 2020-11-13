FROM fedora:32
LABEL MAINTAINER="Freedom of the Press Foundation"
LABEL DESCRIPTION="Alternative CLI for managing Qubes OS VMs"
ARG USERID=1000

RUN echo "Building RPM for Fedora version ${FEDORA_PKGR_VER}"

RUN dnf update -y
RUN dnf install -y \
    make \
    python3-cryptography \
    python3-devel \
    python3-requests \
    python3-setuptools

RUN dnf install -y \
    man

RUN dnf install -y \
    rpm-build rpm-sign rpm

RUN dnf install -y \
    rpmdevtools rpmspectool

RUN dnf install -y \
    rpmrebuild

ENV HOME /home/user
RUN useradd --create-home --home-dir $HOME user \
    && chown -R user:user $HOME && \
    su -c rpmdev-setuptree user

RUN getent passwd $USERID > /dev/null || \
        ( usermod -u ${USERID} user && chown -R user: /home/user )

ENV SOURCE_DATE_EPOCH 40000

ADD . /app
RUN chown user: -R /app
WORKDIR /app
USER user

CMD ["./scripts/build-dom0-rpm"]
