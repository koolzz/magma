/**
 * Copyright (c) 2016-present, Facebook, Inc.
 * All rights reserved.
 *
 * This source code is licensed under the BSD-style license found in the
 * LICENSE file in the root directory of this source tree. An additional grant
 * of patent rights can be found in the PATENTS file in the same directory.
 */
#pragma once

#include <mutex>

#include <lte/protos/policydb.pb.h>
#include <lte/protos/pgw.grpc.pb.h>

#include "GRPCReceiver.h"

using google::protobuf::RepeatedPtrField;
using grpc::Status;

namespace magma {
using namespace lte;

/**
 * PgwClient is the base class for sending dedicated bearer create/delete to PGW
 */
class PgwClient {
 public:
  /**
   * Delete a dedicated bearer
   * @param imsi - msi to identify a UE
   * @param apn_ip_addr - imsi and apn_ip_addrs identify a default bearer
   * @param link_bearer_id - id for identifying link bearer
   * @param flows - flow information required for a dedicated bearer
   * @return true if the operation was successful
   */
  virtual bool delete_dedicated_bearer(
    const std::string &imsi,
    const std::string &apn_ip_addr,
    const uint32_t link_bearer_id,
    const std::vector<PolicyRule> &flows) = 0;

  /**
   * Create a dedicated bearer
   * @param imsi - msi to identify a UE
   * @param apn_ip_addr - imsi and apn_ip_addrs identify a default bearer
   * @param link_bearer_id - id for identifying link bearer
   * @param flows - flow information required for a dedicated bearer
   * @return true if the operation was successful
   */
  virtual bool create_dedicated_bearer(
    const std::string &imsi,
    const std::string &apn_ip_addr,
    const uint32_t link_bearer_id,
    const std::vector<PolicyRule> &flows) = 0;
};

/**
 * AsyncPgwClient implements PgwClient but sends calls
 * asynchronously to PGW.
 */
class AsyncPgwClient : public GRPCReceiver, public PgwClient {
 public:
  AsyncPgwClient();

  AsyncPgwClient(std::shared_ptr<grpc::Channel> pgw_channel);

  /**
   * Delete a dedicated bearer
   * @param imsi - msi to identify a UE
   * @param apn_ip_addr - imsi and apn_ip_addrs identify a default bearer
   * @param link_bearer_id - id for identifying link bearer
   * @param flows - flow information required for a dedicated bearer
   * @return true if the operation was successful
   */
  bool delete_dedicated_bearer(
    const std::string &imsi,
    const std::string &apn_ip_addr,
    const uint32_t link_bearer_id,
    const std::vector<PolicyRule> &flows);

  /**
   * Create a dedicated bearer
   * @param imsi - msi to identify a UE
   * @param apn_ip_addr - imsi and apn_ip_addrs identify a default bearer
   * @param link_bearer_id - id for identifying link bearer
   * @param flows - flow information required for a dedicated bearer
   * @return true if the operation was successful
   */
  bool create_dedicated_bearer(
    const std::string &imsi,
    const std::string &apn_ip_addr,
    const uint32_t link_bearer_id,
    const std::vector<PolicyRule> &flows);

 private:
  static const uint32_t RESPONSE_TIMEOUT = 6; // seconds
  std::unique_ptr<Pgw::Stub> stub_;

 private:
  void delete_dedicated_bearer_rpc(
    const DeleteBearerRequest &request,
    std::function<void(Status, DeleteBearerResult)> callback);

  void create_dedicated_bearer_rpc(
    const CreateBearerRequest &request,
    std::function<void(Status, CreateBearerResult)> callback);
};

} // namespace magma
