# A stand-in for the `core` service, used only by tests/nginx_contract.py.
#
# It answers 200 on every path with a JSON body echoing the path it was asked
# for and the two internal headers it received. That is what lets the contract
# test tell the two interesting failures apart: a request that never arrived
# (the proxy denied it) versus one that arrived at the wrong path (the prefix
# was not re-added).
FROM nginx:1.29-alpine

RUN rm /etc/nginx/conf.d/default.conf
COPY default.conf /etc/nginx/conf.d/default.conf
EXPOSE 8000
